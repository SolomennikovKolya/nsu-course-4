# MD5 crack — отказоустойчивая распределённая система

Менеджер (FastAPI) + воркеры (Python) + RabbitMQ + MongoDB ReplicaSet.

Два варианта запуска:
- **A. docker compose** — прототип, без отказоустойчивости БД.
- **B. Kubernetes (minikube)** — полная конфигурация с replica set Mongo.

---

## A. docker compose (быстрый прототип)

```powershell
docker compose up --build --scale worker=2
```

- Manager API / Swagger: <http://localhost:8000/docs>
- RabbitMQ UI: <http://localhost:15672> (guest / guest)

---

## B. Kubernetes (minikube)

### Предусловия
- `minikube`, `kubectl`, Docker Desktop.
- Запущенный кластер: `minikube start --cpus=4 --memory=6g`.

### Установка

```powershell
# 1. Сборка образов в docker daemon minikube
minikube image build -t crack-manager:latest .\manager
minikube image build -t crack-worker:latest  .\worker

# 2. Инфра (MongoDB ReplicaSet 3 узла + RabbitMQ + ConfigMap)
kubectl apply -f .\k8s\rabbitmq.yaml
kubectl apply -f .\k8s\mongodb.yaml
kubectl apply -f .\k8s\configmap.yaml

# 3. Подождать инициализации replica set (Job mongo-init)
kubectl wait --for=condition=complete --timeout=5m job/mongo-init

# 4. Manager + Worker
kubectl apply -f .\k8s\manager.yaml
kubectl apply -f .\k8s\worker.yaml

# 5. Мониторинг (Prometheus + Grafana + mongodb_exporter)
kubectl apply -f .\k8s\mongodb-exporter.yaml
kubectl apply -f .\k8s\monitoring.yaml

# 6. Получить URL API (NodePort 30080)
minikube service manager --url
```

### Быстрая установка

Запустить скрипт, объединяющий все команды выше:
`powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1`

### Доступ к UI

- `kubectl port-forward svc/manager 8080:8000`: http://localhost:8080/docs
- `kubectl port-forward svc/rabbitmq 15672:15672`: http://localhost:15672 (user/password)
- `kubectl port-forward svc/prometheus 9091:9090`: http://localhost:9091
- `kubectl port-forward svc/grafana 3000:3000`: http://localhost:3000 (anonymous Admin)
- `minikube dashboard`: [web-UI для k8s](http:/localhost:47214/api/v1/namespaces/kubernetes-dashboard/services/http:kubernetes-dashboard:/proxy/#/workloads?namespace=default)

В Grafana автоматически появляется дашборд **«MD5 crack overview»** с панелями:
активные запросы, RPS по ручкам, темпы published/received задач, busy-флаги воркеров,
длина очередей RabbitMQ, состояние членов replica set MongoDB.

### Проверка

`abc` → MD5 = `900150983cd24fb0d6963f7d28e17f72`.

```powershell
$base = (minikube service manager --url)
$body = '{"hash":"900150983cd24fb0d6963f7d28e17f72","maxLength":3}'
$id   = (curl.exe -s -X POST "$base/api/hash/crack" `
            -H "Content-Type: application/json" -d $body | ConvertFrom-Json).requestId

curl.exe -s "$base/api/hash/status?requestId=$id"
```

Хэш из задания: `e2fc714c4727ee9395f324cd2e7f331f` → `abcd`, `maxLength=4`.

### Масштабирование воркеров

```powershell
kubectl scale deployment worker --replicas=4
```

### Тестовые кейсы отказоустойчивости

| Сценарий | Команда | Ожидаемое поведение |
|---|---|---|
| Перезапуск менеджера | `kubectl rollout restart deploy manager` | После старта восстанавливает все незавершённые задачи из Mongo и переотправляет в `task.queue`. |
| Падение primary Mongo | `kubectl delete pod mongo-0` | Один из secondary становится primary; запись/чтение продолжаются, клиент pymongo делает retry. |
| Перезапуск RabbitMQ | `kubectl delete pod rabbitmq-0` | После старта очереди и сообщения на месте (PVC + persistent messages). |
| Падение воркера | `kubectl delete pod -l app=worker --field-selector status.phase=Running` | Задача без `ack` возвращается в очередь, подхватывается другим. |
| Остановка всех воркеров | `kubectl scale deploy worker --replicas=0` | Задачи копятся в `task.queue`; новые crack-запросы принимаются. |
| Недоступность RabbitMQ при POST | `kubectl scale statefulset rabbitmq --replicas=0` → POST → восстановить | Manager сохраняет задачи `PENDING` в Mongo; republish-loop досылает их после восстановления. |

---

## Структура

```
manager/                FastAPI + pika + pymongo + prometheus_client (Dockerfile)
worker/                 pika + hashlib + prometheus_client (Dockerfile)
docker-compose.yml      вариант A
k8s/
  rabbitmq.yaml         StatefulSet(1) + Service (порты 5672/15672/15692)
  mongodb.yaml          StatefulSet(3) + Headless Service + init Job (rs.initiate)
  mongodb-exporter.yaml percona/mongodb_exporter → Prometheus
  configmap.yaml        MONGO_URL, RABBIT_URL, CHUNK_SIZE
  manager.yaml          Deployment + NodePort 30080 (/metrics с counters/gauge)
  worker.yaml           Deployment replicas=2 (/metrics на :9100)
  monitoring.yaml       Prometheus + Grafana + RBAC + dashboard
```
