"""
Worker: тянет задачи из task.queue, перебирает строки, считает MD5,
складывает совпадения в result.queue.

Глобальный индекс задачи — это позиция в последовательности всех строк
длины 1..maxLength в лексикографическом порядке: сначала все длины 1,
потом все длины 2 и т.д. Для алфавита a-z0-9 (36 символов) длина L
имеет 36^L позиций.

Память: храним только текущие «цифры» (digits) длины L; инкрементируем
их как в base-36 (старший разряд — слева, как в itertools.product).
"""

import hashlib
import json
import logging
import os
import socket
import time

import pika
from prometheus_client import Counter, Gauge, start_http_server

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
BASE = len(ALPHABET)

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/")
TASK_QUEUE = "task.queue"
RESULT_QUEUE = "result.queue"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("worker")

METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))
WORKER_ID = socket.gethostname()

# 1 — занят задачей, 0 — простаивает
WORKER_BUSY = Gauge(
    "crack_worker_busy", "1 if worker is processing a task", ["worker"]
)
TASKS = Counter(
    "crack_worker_tasks_total", "Tasks processed", ["worker", "status"]
)
WORKER_BUSY.labels(worker=WORKER_ID).set(0)


def iter_strings(start_idx: int, count: int, max_length: int):
    """Итерируем `count` подряд идущих строк начиная с глобального start_idx."""
    # найдём стартовые (L, local_pos)
    L = 1
    cur = start_idx
    while L <= max_length:
        count_L = BASE ** L
        if cur < count_L:
            break
        cur -= count_L
        L += 1
    if L > max_length:
        return

    produced = 0
    while produced < count and L <= max_length:
        count_L = BASE ** L
        # начальное представление cur в base-36, длина L
        digits = [0] * L
        x = cur
        for i in range(L - 1, -1, -1):
            digits[i] = x % BASE
            x //= BASE

        while cur < count_L and produced < count:
            yield "".join(ALPHABET[d] for d in digits)
            cur += 1
            produced += 1
            # инкремент digits как многоразрядного счётчика (старший слева)
            j = L - 1
            while j >= 0:
                digits[j] += 1
                if digits[j] < BASE:
                    break
                digits[j] = 0
                j -= 1

        # переход на следующую длину
        L += 1
        cur = 0


def process_task(msg: dict) -> dict:
    target = msg["targetHash"].lower()
    found: list[str] = []
    for s in iter_strings(msg["startIndex"], msg["count"], msg["maxLength"]):
        if hashlib.md5(s.encode()).hexdigest() == target:
            found.append(s)
    return {
        "taskId": msg["taskId"],
        "requestId": msg["requestId"],
        "results": found,
        "status": "DONE",
    }


def on_message(ch, method, _props, body):
    WORKER_BUSY.labels(worker=WORKER_ID).set(1)
    try:
        msg = json.loads(body)
        log.info(
            "task %s req=%s start=%d count=%d",
            msg["taskId"], msg["requestId"], msg["startIndex"], msg["count"],
        )
        t0 = time.time()
        result = process_task(msg)
        log.info(
            "task %s done in %.2fs, found=%d",
            msg["taskId"], time.time() - t0, len(result["results"]),
        )
        ch.basic_publish(
            exchange="",
            routing_key=RESULT_QUEUE,
            body=json.dumps(result).encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        TASKS.labels(worker=WORKER_ID, status="success").inc()
    except Exception as e:
        log.exception("task processing failed: %s", e)
        TASKS.labels(worker=WORKER_ID, status="error").inc()
        # вернём в очередь — другой воркер попробует
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    finally:
        WORKER_BUSY.labels(worker=WORKER_ID).set(0)


def main():
    start_http_server(METRICS_PORT)
    log.info("metrics on :%d/metrics", METRICS_PORT)
    while True:
        try:
            conn = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
            ch = conn.channel()
            ch.queue_declare(queue=TASK_QUEUE, durable=True)
            ch.queue_declare(queue=RESULT_QUEUE, durable=True)
            ch.basic_qos(prefetch_count=1)  # по одной задаче за раз
            ch.basic_consume(queue=TASK_QUEUE, on_message_callback=on_message)
            log.info("worker ready, waiting for tasks")
            ch.start_consuming()
        except Exception as e:
            log.warning("connection lost, reconnect in 3s: %s", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
