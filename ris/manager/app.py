"""
Manager: REST API + публикация задач в RabbitMQ + потребитель результатов.

Логика:
- POST /api/hash/crack — режем пространство комбинаций (длины 1..maxLength,
  алфавит a-z0-9) на чанки по CHUNK_SIZE, сохраняем все задачи в Mongo
  (write concern majority), отвечаем клиенту, потом публикуем в task.queue.
- GET /api/hash/status — отдаём агрегированный статус по requestId.
- Фоновый поток consume_results — слушает result.queue, мёрджит результаты
  в Mongo идемпотентно (повторная доставка одной задачи не ломает счётчик).
- При старте republish_pending: всё, что не DONE — повторно публикуем
  (чтобы пережить падение менеджера и недоступность RabbitMQ).
"""

import json
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

import pika
from fastapi import FastAPI, HTTPException, Query, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest,
)
from pydantic import BaseModel, Field, field_validator
from pymongo import MongoClient, ReturnDocument

# ---------- конфигурация ----------

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
BASE = len(ALPHABET)

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "100000"))
MAX_ALLOWED_LENGTH = int(os.getenv("MAX_ALLOWED_LENGTH", "5"))

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/")

TASK_QUEUE = "task.queue"
RESULT_QUEUE = "result.queue"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("manager")

# ---------- Mongo ----------

mongo = MongoClient(MONGO_URL, w="majority")
db = mongo["crack"]
requests_col = db["requests"]
tasks_col = db["tasks"]
tasks_col.create_index("requestId")
tasks_col.create_index("status")

# ---------- метрики ----------

REQS = Counter(
    "crack_http_requests_total",
    "HTTP requests by handler and status code",
    ["handler", "code"],
)
TASKS_PUBLISHED = Counter(
    "crack_tasks_published_total", "Tasks published to RabbitMQ"
)
TASKS_PUBLISH_FAILED = Counter(
    "crack_tasks_publish_failed_total", "Failed task publish attempts"
)
RESULTS_RECEIVED = Counter(
    "crack_results_received_total", "Results consumed from result.queue",
)
ACTIVE_REQUESTS = Gauge(
    "crack_active_requests", "Requests currently in IN_PROGRESS state",
)

# ---------- RabbitMQ (publisher) ----------
# pika.BlockingConnection не потокобезопасна — защищаем единым lock.

_pub_lock = threading.Lock()
_pub_conn: pika.BlockingConnection | None = None
_pub_ch = None


def _ensure_publisher():
    global _pub_conn, _pub_ch
    if _pub_ch is not None and not _pub_ch.is_closed:
        return _pub_ch
    _pub_conn = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
    _pub_ch = _pub_conn.channel()
    _pub_ch.queue_declare(queue=TASK_QUEUE, durable=True)
    _pub_ch.queue_declare(queue=RESULT_QUEUE, durable=True)
    return _pub_ch


def publish_task(task: dict) -> bool:
    """Best-effort публикация. False — если RabbitMQ недоступен."""
    try:
        with _pub_lock:
            ch = _ensure_publisher()
            ch.basic_publish(
                exchange="",
                routing_key=TASK_QUEUE,
                body=json.dumps(task).encode(),
                properties=pika.BasicProperties(delivery_mode=2),  # persistent
            )
        TASKS_PUBLISHED.inc()
        return True
    except Exception as e:
        TASKS_PUBLISH_FAILED.inc()
        log.warning("publish_task failed: %s", e)
        # сбрасываем соединение, чтобы переподключиться при следующей попытке
        global _pub_conn, _pub_ch
        try:
            if _pub_conn is not None:
                _pub_conn.close()
        except Exception:
            pass
        _pub_conn = None
        _pub_ch = None
        return False


# ---------- result consumer ----------


def _on_result(ch, method, _props, body):
    """Идемпотентная обработка результата задачи."""
    try:
        msg = json.loads(body)
        task_id = msg["taskId"]
        request_id = msg["requestId"]
        results = msg.get("results", []) or []
        status = msg.get("status", "DONE")

        # Атомарно помечаем задачу DONE только если она ещё не DONE.
        # Если find_one_and_update вернул документ — значит мы переключили
        # её сейчас и должны инкрементнуть счётчик в request.
        first_time = tasks_col.find_one_and_update(
            {"_id": task_id, "status": {"$ne": "DONE"}},
            {"$set": {"status": "DONE", "finishedAt": time.time(),
                      "workerStatus": status, "workerResults": results}},
            return_document=ReturnDocument.AFTER,
        )
        if first_time is not None:
            RESULTS_RECEIVED.inc()
            upd = {"$inc": {"doneTasks": 1}}
            if results:
                upd["$addToSet"] = {"results": {"$each": results}}
            req = requests_col.find_one_and_update(
                {"_id": request_id}, upd, return_document=ReturnDocument.AFTER
            )
            if req and req["doneTasks"] >= req["totalTasks"]:
                requests_col.update_one(
                    {"_id": request_id},
                    {"$set": {"status": "READY", "finishedAt": time.time()}},
                )
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        log.exception("result handler error: %s", e)
        # вернуть в очередь — пусть кто-нибудь попробует ещё раз
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def consume_results():
    """Бесконечный потребитель result.queue. Переподключается при обрывах."""
    while True:
        try:
            conn = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
            ch = conn.channel()
            ch.queue_declare(queue=RESULT_QUEUE, durable=True)
            ch.basic_qos(prefetch_count=10)
            ch.basic_consume(queue=RESULT_QUEUE, on_message_callback=_on_result)
            log.info("result consumer started")
            ch.start_consuming()
        except Exception as e:
            log.warning("result consumer reconnecting in 3s: %s", e)
            time.sleep(3)


# ---------- republisher (восстановление при старте + retry для PENDING) ----------


def republish_loop():
    """
    На старте — переотправляем всё, что не DONE.
    Дальше периодически дослыем PENDING (это те задачи, которые при создании
    не удалось положить в очередь, например, из-за временной недоступности
    RabbitMQ).
    """
    # начальная попытка: переотправить всё, что не DONE
    while True:
        try:
            for t in tasks_col.find({"status": {"$ne": "DONE"}}):
                ok = publish_task({
                    "taskId": t["_id"],
                    "requestId": t["requestId"],
                    "startIndex": t["startIndex"],
                    "count": t["count"],
                    "targetHash": t["targetHash"],
                    "maxLength": t["maxLength"],
                })
                if ok and t["status"] == "PENDING":
                    tasks_col.update_one(
                        {"_id": t["_id"], "status": "PENDING"},
                        {"$set": {"status": "QUEUED"}},
                    )
            log.info("startup republish pass complete")
            break
        except Exception as e:
            log.warning("startup republish failed, retrying in 3s: %s", e)
            time.sleep(3)

    # затем — только PENDING каждые 5 секунд
    while True:
        try:
            time.sleep(5)
            pending = list(tasks_col.find({"status": "PENDING"}))
            if not pending:
                continue
            log.info("retrying %d PENDING tasks", len(pending))
            for t in pending:
                ok = publish_task({
                    "taskId": t["_id"],
                    "requestId": t["requestId"],
                    "startIndex": t["startIndex"],
                    "count": t["count"],
                    "targetHash": t["targetHash"],
                    "maxLength": t["maxLength"],
                })
                if ok:
                    tasks_col.update_one(
                        {"_id": t["_id"], "status": "PENDING"},
                        {"$set": {"status": "QUEUED"}},
                    )
        except Exception as e:
            log.warning("retry loop error: %s", e)


# ---------- FastAPI ----------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=consume_results, daemon=True).start()
    threading.Thread(target=republish_loop, daemon=True).start()
    log.info("manager started")
    yield


app = FastAPI(title="MD5 crack manager", lifespan=lifespan)


@app.middleware("http")
async def _metrics_mw(request: Request, call_next):
    # /metrics сам себя не считаем — иначе бесконечный кост вызова
    response = await call_next(request)
    path = request.url.path
    # схлопываем динамические части до имени ручки
    if path.startswith("/api/hash/crack"):
        handler = "crack"
    elif path.startswith("/api/hash/status"):
        handler = "status"
    elif path == "/healthz":
        handler = "healthz"
    elif path == "/metrics":
        return response
    else:
        handler = "other"
    REQS.labels(handler=handler, code=str(response.status_code)).inc()
    return response


@app.get("/metrics")
def metrics():
    # обновим gauge активных запросов на каждом скрэйпе
    ACTIVE_REQUESTS.set(requests_col.count_documents({"status": "IN_PROGRESS"}))
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class CrackRequest(BaseModel):
    hash: str = Field(..., min_length=32, max_length=32)
    maxLength: int = Field(..., ge=1, le=MAX_ALLOWED_LENGTH)

    @field_validator("hash")
    @classmethod
    def _norm_hash(cls, v: str) -> str:
        v = v.strip().lower()
        int(v, 16)  # бросит ValueError если не hex
        return v


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/api/hash/crack")
def crack(req: CrackRequest):
    request_id = str(uuid.uuid4())
    total = sum(BASE ** L for L in range(1, req.maxLength + 1))

    # 1) формируем список задач
    tasks_docs = []
    offset = 0
    while offset < total:
        count = min(CHUNK_SIZE, total - offset)
        tasks_docs.append({
            "_id": str(uuid.uuid4()),
            "requestId": request_id,
            "startIndex": offset,
            "count": count,
            "targetHash": req.hash,
            "maxLength": req.maxLength,
            "status": "PENDING",
            "createdAt": time.time(),
        })
        offset += count

    # 2) сохраняем в Mongo (w=majority — клиенту отвечаем только после этого)
    requests_col.insert_one({
        "_id": request_id,
        "hash": req.hash,
        "maxLength": req.maxLength,
        "totalTasks": len(tasks_docs),
        "doneTasks": 0,
        "results": [],
        "status": "IN_PROGRESS",
        "createdAt": time.time(),
    })
    if tasks_docs:
        tasks_col.insert_many(tasks_docs)

    # 3) пытаемся опубликовать в RabbitMQ; неотправленные останутся PENDING
    #    и будут добиты republish_loop'ом.
    for t in tasks_docs:
        ok = publish_task({
            "taskId": t["_id"],
            "requestId": request_id,
            "startIndex": t["startIndex"],
            "count": t["count"],
            "targetHash": req.hash,
            "maxLength": req.maxLength,
        })
        if ok:
            tasks_col.update_one(
                {"_id": t["_id"], "status": "PENDING"},
                {"$set": {"status": "QUEUED"}},
            )

    return {"requestId": request_id}


@app.get("/api/hash/status")
def status(requestId: str = Query(...)):
    doc = requests_col.find_one({"_id": requestId})
    if doc is None:
        raise HTTPException(status_code=404, detail="unknown requestId")
    if doc["status"] == "READY":
        return {"status": "READY", "results": doc.get("results", [])}
    if doc["status"] == "ERROR":
        return {"status": "ERROR"}
    return {"status": "IN_PROGRESS"}
