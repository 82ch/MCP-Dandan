# 82ch-UI Backend Dockerfile
FROM node:20-alpine

WORKDIR /app

# SQLite3 네이티브 바인딩을 위한 빌드 도구 설치 (먼저 설치)
RUN apk add --no-cache python3 make g++ sqlite

# 패키지 파일 복사 및 의존성 설치
COPY package*.json ./
RUN npm install

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 3001

# 서버 실행
CMD ["npm", "start"]
