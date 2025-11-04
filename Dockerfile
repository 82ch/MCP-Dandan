# 82ch-engine Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 데이터 디렉토리 생성
RUN mkdir -p /app/data

# 데이터베이스 볼륨
VOLUME ["/app/data"]

# 포트 노출 (ZeroMQ)
EXPOSE 5555

# 엔진 실행
CMD ["python", "engine_server.py"]
