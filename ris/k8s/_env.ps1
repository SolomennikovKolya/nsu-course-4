# Дополняет PATH текущей сессии путями к minikube и helm.
# Использование: . .\k8s\_env.ps1
$env:Path = "C:\Program Files\Kubernetes\Minikube;" +
            "C:\Users\solom\AppData\Local\Microsoft\WinGet\Packages\Helm.Helm_Microsoft.Winget.Source_8wekyb3d8bbwe\windows-amd64;" +
            $env:Path
