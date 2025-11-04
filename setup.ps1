# 82ch-engine 자동 설정 스크립트 (Windows PowerShell)

Write-Host "========================================"
Write-Host "82ch-engine Setup Script"
Write-Host "========================================"
Write-Host ""

# Docker 설치 확인
try {
    $dockerVersion = docker --version
    Write-Host "✅ Docker: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker가 설치되어 있지 않습니다." -ForegroundColor Red
    Write-Host "Docker Desktop을 설치하세요: https://www.docker.com/products/docker-desktop/"
    exit 1
}

try {
    $composeVersion = docker-compose --version
    Write-Host "✅ Docker Compose: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose가 설치되어 있지 않습니다." -ForegroundColor Red
    exit 1
}

Write-Host ""

# 기존 컨테이너 중지
Write-Host "🛑 기존 컨테이너 중지 중..." -ForegroundColor Yellow
docker-compose down 2>$null
Write-Host ""

# 데이터 디렉토리 생성
Write-Host "📁 데이터 디렉토리 생성 중..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "data" | Out-Null
Write-Host ""

# Docker 이미지 빌드 및 실행
Write-Host "🔨 Docker 이미지 빌드 및 실행 중..." -ForegroundColor Yellow
docker-compose up -d --build
Write-Host ""

# 컨테이너 시작 대기
Write-Host "⏳ 컨테이너 시작 대기 중..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
Write-Host ""

# 상태 확인
Write-Host "📊 서비스 상태:" -ForegroundColor Cyan
docker-compose ps
Write-Host ""

# 접속 정보 출력
Write-Host "========================================"
Write-Host "✅ 설치 완료!" -ForegroundColor Green
Write-Host "========================================"
Write-Host ""
Write-Host "🔌 ZeroMQ Publisher: tcp://localhost:5555"
Write-Host "💾 데이터베이스 경로: .\data\mcp_observer.db"
Write-Host ""
Write-Host "  - db간단히 조회: python .\query_db.py"
Write-Host ""
