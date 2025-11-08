# 82ch-engine 자동 설정 스크립트 (Windows PowerShell)

Write-Host "========================================"
Write-Host "82ch-engine Setup Script"
Write-Host "========================================"
Write-Host ""

# Docker 설치 확인
try {
    $dockerVersion = docker --version
    Write-Host "Docker: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "Docker is not installed" -ForegroundColor Red
    Write-Host "you should install docker : https://www.docker.com/products/docker-desktop/"
    exit 1
}

try {
    $composeVersion = docker-compose --version
    Write-Host "Docker Compose: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "Docker Compose가 설치되어 있지 않습니다." -ForegroundColor Red
    exit 1
}

Write-Host ""

# 기존 컨테이너 중지
Write-Host "Stopping existing containers..." -ForegroundColor Yellow
docker-compose down 2>$null
Write-Host ""

# 데이터 디렉토리 생성
Write-Host "Creating data directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "data" | Out-Null
Write-Host ""

# Docker 이미지 빌드 및 실행
Write-Host "Building and running Docker image..." -ForegroundColor Yellow
docker-compose up -d --build
Write-Host ""

# 컨테이너 시작 대기
Write-Host "Waiting for container to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
Write-Host ""

# 상태 확인
Write-Host "Service status:" -ForegroundColor Cyan
docker-compose ps
Write-Host ""

# 접속 정보 출력
Write-Host "========================================"
Write-Host "installed Complete!" -ForegroundColor Green
Write-Host "========================================"
Write-Host ""
Write-Host "ZeroMQ Publisher: tcp://localhost:5555"
Write-Host "Database Path: .\data\mcp_observer.db"
Write-Host ""
Write-Host " -simply lookup db : python .\query_db.py"
Write-Host ""
