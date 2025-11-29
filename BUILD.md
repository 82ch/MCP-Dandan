# 82ch Desktop 애플리케이션 빌드 가이드

이 문서는 82ch Desktop 애플리케이션을 Linux에서 실행 가능한 형태로 패키징하는 방법을 설명합니다.

## 사전 요구사항

- Node.js 18 이상
- Python 3.8 이상
- Linux 시스템 (Ubuntu 20.04 이상 권장)

## 설치

### 1. 의존성 설치

```bash
# 루트 디렉토리에서
npm install

# 프론트엔드 디렉토리에서
cd front
npm install --legacy-peer-deps
```

### 2. Python 의존성 설치

```bash
# 루트 디렉토리에서
pip install -r requirements.txt
```

## 빌드 방법

### Linux용 배포 패키지 생성

```bash
cd front
npm run dist:linux
```

이 명령어는 다음을 생성합니다:
- **AppImage**: 모든 Linux 배포판에서 실행 가능한 단일 실행 파일
- **DEB 패키지**: Debian/Ubuntu 계열에서 설치 가능한 패키지

생성된 파일은 `front/release/` 디렉토리에 저장됩니다.

### 다른 플랫폼 빌드

```bash
# Windows용 (Windows 시스템에서만 가능)
cd front
npm run dist

# 개발 빌드만 (패키징 없이)
cd front
npm run build
```

## Linux에서 실행하기

### 빠른 설치 (권장)

빌드 후 한 번의 명령으로 설치:

```bash
./quick-install.sh
```

이 스크립트는 자동으로:
- 빌드된 패키지 감지
- DEB 또는 AppImage 설치 선택 제공
- 데스크톱 엔트리 생성
- PATH 설정 안내

### 수동 설치

#### AppImage 실행

```bash
cd front/release

# 실행 권한 부여
chmod +x 82ch-Desktop-*.AppImage

# 더블클릭하거나 터미널에서 실행
./82ch-Desktop-*.AppImage
```

#### DEB 패키지 설치

```bash
cd front/release

# DEB 패키지 설치
sudo dpkg -i 82ch-desktop_*.deb

# 의존성 문제 해결 (필요한 경우)
sudo apt-get install -f

# 설치 후 애플리케이션 메뉴에서 "82ch Desktop" 검색하여 실행
```

### 원격 설치 (GitHub Release 필요)

프로젝트가 GitHub에 배포되면 Tailscale처럼 한 줄로 설치 가능:

```bash
curl -fsSL https://raw.githubusercontent.com/your-org/82ch/main/install.sh | sudo bash
```

## 개발 모드 실행

빌드하지 않고 개발 모드로 실행하려면:

```bash
# 루트 디렉토리에서
npm run dev
```

이 명령어는 다음을 동시에 실행합니다:
- Python 백엔드 서버 (server.py)
- Electron + Vite 프론트엔드

## 주의사항

### Python 서버 포함

현재 빌드 설정은 Python 서버 파일들을 `extraResources`로 포함하도록 구성되어 있습니다.
애플리케이션 실행 시 Python이 시스템에 설치되어 있어야 합니다.

### 데이터베이스 경로

프로덕션 모드에서는 사용자 데이터 디렉토리에 데이터베이스가 생성됩니다:
- **Linux**: `~/.config/82ch Desktop/data/mcp_observer.db`
- **Windows**: `%APPDATA%\82ch Desktop\data\mcp_observer.db`
- **macOS**: `~/Library/Application Support/82ch Desktop/data/mcp_observer.db`

개발 모드에서는 프로젝트 루트의 `data/mcp_observer.db`를 사용합니다.

### 백엔드 로그 확인

프로덕션 모드에서 백엔드 로그는 Electron 콘솔에 표시됩니다:
- **Linux/macOS**: 터미널에서 실행 시 `[Backend]` 접두사로 표시
- **Windows**: 개발자 도구 콘솔에서 확인 가능

개발 모드:
```bash
npm run dev  # 백엔드와 프론트엔드 로그가 모두 터미널에 표시됨
```

### 아이콘 추가 (선택사항)

커스텀 아이콘을 사용하려면:

1. 512x512 픽셀 PNG 이미지 준비
2. `front/build-resources/icon.png`로 저장
3. 빌드 재실행

## 트러블슈팅

### 빌드 실패 시

1. Node modules 재설치:
```bash
cd front
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

2. Native 모듈 재빌드:
```bash
cd front
npm run rebuild-native
```

### 실행 시 오류

1. Python 의존성 확인:
```bash
pip install -r requirements.txt
```

2. 포트 충돌 확인 (8282 포트 사용 중인지):
```bash
lsof -i:8282
```

## 배포 파일 구조

```
release/
├── 82ch-Desktop-1.0.0.AppImage    # AppImage 실행 파일
├── 82ch-desktop_1.0.0_amd64.deb   # DEB 패키지
└── builder-debug.yml              # 빌드 디버그 정보
```

## 추가 정보

- 애플리케이션 ID: `com.82ch.desktop`
- 기본 설치 경로 (DEB): `/opt/82ch Desktop/`
- 사용자 데이터 경로: `~/.config/82ch Desktop/`
