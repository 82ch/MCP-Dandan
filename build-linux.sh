#!/bin/bash

# 82ch Desktop Linux 빌드 스크립트

set -e

echo "================================"
echo "82ch Desktop Linux 빌드 시작"
echo "================================"

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 현재 디렉토리 저장
ROOT_DIR=$(pwd)

# Node.js 버전 확인
echo -e "\n${BLUE}[1/5] Node.js 버전 확인...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js가 설치되어 있지 않습니다.${NC}"
    exit 1
fi
echo "Node.js 버전: $(node --version)"

# Python 버전 확인
echo -e "\n${BLUE}[2/5] Python 버전 확인...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3가 설치되어 있지 않습니다.${NC}"
    exit 1
fi
echo "Python 버전: $(python3 --version)"

# 의존성 설치 확인
echo -e "\n${BLUE}[3/5] 의존성 확인 및 설치...${NC}"
cd "$ROOT_DIR/front"

if [ ! -d "node_modules" ]; then
    echo "npm 의존성 설치 중..."
    npm install --legacy-peer-deps
else
    echo "npm 의존성이 이미 설치되어 있습니다."
fi

# TypeScript 빌드
echo -e "\n${BLUE}[4/5] TypeScript 컴파일 및 Vite 빌드...${NC}"
npm run build

# Linux 패키지 생성
echo -e "\n${BLUE}[5/5] Linux 배포 패키지 생성...${NC}"
npx electron-builder --linux

echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}빌드 완료!${NC}"
echo -e "${GREEN}================================${NC}"

# 생성된 파일 목록 표시
echo -e "\n생성된 파일:"
ls -lh "$ROOT_DIR/front/release/" | grep -E '\.(AppImage|deb)$' || echo "패키지 파일을 찾을 수 없습니다."

echo -e "\n${GREEN}AppImage 실행 방법:${NC}"
echo "  cd front/release"
echo "  chmod +x *.AppImage"
echo "  ./82ch-Desktop-*.AppImage"

echo -e "\n${GREEN}DEB 패키지 설치 방법:${NC}"
echo "  cd front/release"
echo "  sudo dpkg -i 82ch-desktop_*.deb"
