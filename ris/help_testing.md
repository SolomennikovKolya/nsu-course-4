
## 1. Как отправить запрос

### Через PowerShell (для скриптов)
```powershell
$r = Invoke-RestMethod -Uri http://localhost:8080/api/hash/crack -Method Post `
     -ContentType "application/json" `
     -Body '{"hash":"e2fc714c4727ee9395f324cd2e7f331f","maxLength":4}'
$id = $r.requestId
Invoke-RestMethod "http://localhost:8080/api/hash/status?requestId=$id"
```

### Полезные тестовые хэши
| MD5 | строка | `maxLength` | время |
|---|---|---|---|
| `900150983cd24fb0d6963f7d28e17f72` | `abc` | 3 | ~1 сек |
| `e2fc714c4727ee9395f324cd2e7f331f` | `abcd` | 4 | ~6 сек |
| `deadbeefdeadbeefdeadbeefdeadbeef` | (нет) | 5 | ~2 мин (длинный кейс — не найдётся) |

Сделать свой: `python -c "import hashlib;print(hashlib.md5(b'hi42').hexdigest())"`.

---

## 2. Сценарии отказоустойчивости — точные команды

Все приведённые команды безопасные — данные не теряются (на то она и отказоустойчивость).

### Кейс 1: Перезапуск менеджера
```powershell
kubectl rollout restart deploy/manager
# или жёстко:
kubectl delete pod -l app=manager --grace-period=0 --force
```
Подавай запрос **до** удаления — он останется в Mongo как `IN_PROGRESS`, после рестарта manager перепошлёт незавершённые задачи. Через секунды статус станет `READY`.

### Кейс 2: Failover primary MongoDB
```powershell
# узнать, кто сейчас primary
kubectl exec mongo-0 -- mongosh --quiet --eval "rs.status().members.filter(m=>m.stateStr==='PRIMARY')[0].name"
# убить его (подставь имя из вывода выше)
kubectl delete pod mongo-0 --grace-period=0 --force
# сразу подать запрос — он должен пройти, pymongo сам найдёт нового primary
```

### Кейс 3: Перезапуск RabbitMQ
```powershell
kubectl delete pod rabbitmq-0 --grace-period=0 --force
# в Grafana увидишь провал «RabbitMQ queue depth», но очереди вернутся с тем же содержимым
```

### Кейс 4: Падение воркера во время задачи
```powershell
# делаем долгую задачу (60M комбинаций)
$r = Invoke-RestMethod -Uri http://localhost:8080/api/hash/crack -Method Post `
     -ContentType "application/json" `
     -Body '{"hash":"deadbeefdeadbeefdeadbeefdeadbeef","maxLength":5}'
# смотрим в Grafana как очередь набивается, потом убиваем одного воркера
kubectl delete pod -l app=worker --grace-period=0 --force
# проверяем статус позже — должен прийти к READY
Invoke-RestMethod "http://localhost:8080/api/hash/status?requestId=$($r.requestId)"
```

### Кейс 5: Все воркеры остановлены
```powershell
kubectl scale deploy worker --replicas=0
# отправляем запрос — задачи копятся, статус IN_PROGRESS
# возвращаем воркеров
kubectl scale deploy worker --replicas=2
```

### Кейс 6: RabbitMQ недоступен на момент POST
```powershell
kubectl scale statefulset rabbitmq --replicas=0
# POST всё равно принимается, задачи лежат в Mongo как PENDING
$r = Invoke-RestMethod -Uri http://localhost:8080/api/hash/crack -Method Post `
     -ContentType "application/json" `
     -Body '{"hash":"900150983cd24fb0d6963f7d28e17f72","maxLength":3}'
# проверить, что в Mongo есть PENDING:
kubectl exec mongo-1 -- mongosh --quiet --eval "db.getSiblingDB('crack').tasks.find({status:'PENDING'}).count()"
# возвращаем RabbitMQ
kubectl scale statefulset rabbitmq --replicas=1
# republish_loop досылает раз в 5 секунд — через 10-15 сек получишь READY
```

---

## 3. Где смотреть, что происходит

| Что | Где |
|---|---|
| **Текущее состояние подов / логи / exec в контейнер** | `minikube dashboard` или `kubectl get pods` / `kubectl logs <pod>` |
| **Графики метрик (RPS, занятость воркеров, длина очередей)** | **Grafana** [http://localhost:3000](http://localhost:3000), дашборд «MD5 crack overview» |
| **Очереди RabbitMQ: сообщения, ack'и, поток сообщений в реальном времени** | **RabbitMQ UI** [http://localhost:15672](http://localhost:15672) → вкладка **Queues** |
| **Сырые метрики Prometheus + PromQL запросы** | [http://localhost:9091](http://localhost:9091) → Graph |
| **Состояние replica set Mongo** | `kubectl exec mongo-0 -- mongosh --eval "rs.status()"` |
| **Содержимое БД** | `kubectl exec mongo-0 -- mongosh --eval "db.getSiblingDB('crack').requests.find().pretty()"` |
| **Логи менеджера в реальном времени** | `kubectl logs -f -l app=manager` |
| **Логи всех воркеров** | `kubectl logs -f -l app=worker --max-log-requests=5` |

### Самое наглядное — открыть три вкладки и крутить запросы
1. **RabbitMQ UI → Queues** — видишь как `task.queue` распухает на POST и сдувается по мере обработки.
2. **Grafana → MD5 crack overview** — графики RPS, busy/idle воркеров, depth очередей.
3. **Dashboard minikube → Pods** — видно `Restarts` и текущее состояние подов после kill-команд.

---

## 4. Где менять параметры

**Веб-интерфейса для редактирования конфига нет** — ни в Kubernetes из коробки, ни в dashboard. Конфиг — это yaml-файлы в [k8s/](k8s/).

### Что где лежит

| Параметр | Файл | Поле |
|---|---|---|
| URL MongoDB | [k8s/configmap.yaml](k8s/configmap.yaml) | `MONGO_URL` |
| URL RabbitMQ + логин/пароль | [k8s/configmap.yaml](k8s/configmap.yaml) | `RABBIT_URL` |
| Размер чанка задач (комбинаций на задачу) | [k8s/configmap.yaml](k8s/configmap.yaml) | `CHUNK_SIZE` |
| Максимальная разрешённая длина строки | [k8s/configmap.yaml](k8s/configmap.yaml) | `MAX_ALLOWED_LENGTH` |
| Количество воркеров | [k8s/worker.yaml](k8s/worker.yaml) | `spec.replicas` (или `kubectl scale`) |
| Лимиты CPU/RAM | в каждом yaml | `resources.requests` / `resources.limits` |
| Логин/пароль RabbitMQ | [k8s/rabbitmq.yaml](k8s/rabbitmq.yaml) | env `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` |
| Размер дисков (PVC) | [k8s/mongodb.yaml](k8s/mongodb.yaml), [k8s/rabbitmq.yaml](k8s/rabbitmq.yaml) | `volumeClaimTemplates.spec.resources.requests.storage` (только при создании, ресайз отдельной операцией) |

### Как применить изменения

```powershell
# 1. меняешь yaml
notepad .\k8s\configmap.yaml

# 2. применяешь
kubectl apply -f .\k8s\configmap.yaml

# 3. ConfigMap-изменения НЕ перезагружают поды автоматически.
#    Нужно явно сказать «пересоздай поды» (они подхватят новый ConfigMap):
kubectl rollout restart deploy/manager deploy/worker
```

**Важный момент про ConfigMap:** k8s сам не пересоздаёт поды при изменении ConfigMap. ENV-переменные читаются только при старте контейнера. Поэтому всегда: `apply` → `rollout restart`.

### Если поменял код менеджера/воркера

```powershell
minikube image build -t crack-manager:latest .\manager   # или .\worker
kubectl rollout restart deploy/manager                    # или deploy/worker
```
`rollout restart` создаст новые поды, которые при старте подтянут свежий образ из локального registry minikube.

### Live-правка прямо в кластере (для быстрых экспериментов)
```powershell
kubectl edit configmap crack-config        # откроет в редакторе
kubectl edit deployment worker             # тоже работает
```
Это редактирует объект в etcd и применяется мгновенно. Удобно для проб, но потом не забыть синхронизовать с yaml-файлом в репо, иначе при `kubectl apply` поправки откатятся.

---

## Минимальный сценарий «всё посмотреть за 5 минут»

1. Открой 4 вкладки: [Swagger](http://localhost:8080/docs), [RabbitMQ](http://localhost:15672), [Grafana](http://localhost:3000), `minikube dashboard`.
2. В Swagger подай 5 запросов с `maxLength: 4` подряд → смотри как в RabbitMQ → Queues растёт `task.queue`, а в Grafana поднимаются графики «Workers busy» и «Tasks published».
3. В соседнем терминале: `kubectl delete pod -l app=worker --grace-period=0 --force` → в dashboard минikube увидишь, как воркеры пересоздаются, в Grafana «Workers busy» дёргается.
4. Проверь, что все 5 запросов всё равно дошли до `READY` через статус-ручку.
