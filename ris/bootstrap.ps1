# Полная установка системы в minikube с нуля.
# Идемпотентно: повторный запуск не сломает существующий кластер.
$ErrorActionPreference = "Stop"
$env:Path = "C:\Program Files\Kubernetes\Minikube;" +
            "C:\Users\solom\AppData\Local\Microsoft\WinGet\Packages\Helm.Helm_Microsoft.Winget.Source_8wekyb3d8bbwe\windows-amd64;" +
            $env:Path

Write-Host "==> minikube start" -ForegroundColor Cyan
minikube status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    minikube start --cpus=4 --memory=6g
}

Write-Host "==> building images" -ForegroundColor Cyan
minikube image build -t crack-manager:latest .\manager
minikube image build -t crack-worker:latest  .\worker

Write-Host "==> applying infra" -ForegroundColor Cyan
kubectl apply -f .\k8s\rabbitmq.yaml `
              -f .\k8s\mongodb.yaml `
              -f .\k8s\mongodb-exporter.yaml `
              -f .\k8s\configmap.yaml

Write-Host "==> waiting for mongo-init Job" -ForegroundColor Cyan
kubectl wait --for=condition=complete --timeout=8m job/mongo-init

Write-Host "==> applying app + monitoring" -ForegroundColor Cyan
kubectl apply -f .\k8s\manager.yaml `
              -f .\k8s\worker.yaml `
              -f .\k8s\monitoring.yaml

Write-Host "==> rollout (для подхвата свежих образов)" -ForegroundColor Cyan
kubectl rollout restart deploy/manager deploy/worker
kubectl rollout status deploy/manager --timeout=3m
kubectl rollout status deploy/worker  --timeout=3m
kubectl wait --for=condition=available --timeout=4m `
    deploy/prometheus deploy/grafana deploy/mongodb-exporter

Write-Host "==> done. UI:" -ForegroundColor Green
Write-Host "  kubectl port-forward svc/manager    8080:8000"
Write-Host "  kubectl port-forward svc/rabbitmq   15672:15672"
Write-Host "  kubectl port-forward svc/prometheus 9091:9090"
Write-Host "  kubectl port-forward svc/grafana    3000:3000"
