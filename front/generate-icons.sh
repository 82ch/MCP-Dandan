#!/bin/bash

# Linux용 아이콘 생성 스크립트
# 사용법: ./generate-icons.sh

# 필요한 아이콘 크기들
SIZES=(16 24 32 48 64 72 96 128 256 512 1024)

echo "아이콘 생성 중..."

# icons 디렉토리가 존재하는지 확인
if [ ! -f "icons/dandan.png" ]; then
    echo "Error: icons/dandan.png 파일이 없습니다."
    exit 1
fi

# ImageMagick 설치 확인
if ! command -v convert &> /dev/null; then
    echo "ImageMagick이 설치되어 있지 않습니다. 설치 중..."
    sudo apt-get update
    sudo apt-get install -y imagemagick
fi

# 각 크기별로 아이콘 생성
for size in "${SIZES[@]}"; do
    echo "  ${size}x${size} 아이콘 생성..."
    convert icons/dandan.png -resize ${size}x${size} icons/${size}x${size}.png
done

echo "아이콘 생성 완료!"
echo "생성된 파일:"
ls -lh icons/*.png
