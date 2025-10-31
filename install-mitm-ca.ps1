<#
install-mitm-ca-cert-only.ps1
- 관리자 권한으로 실행하세요 (UAC 필요)
- 가정: mitmproxy가 이미 설치되어 있고, CA 파일이 %USERPROFILE%\.mitmproxy 에 존재하거나 mitmdump 실행이 가능함.
- 기능:
  1) %USERPROFILE%\.mitmproxy 폴더에서 mitmproxy CA 파일 (.cer 또는 .pem) 찾기
  2) CA 파일이 없으면 mitmdump를 잠깐 실행하여 CA 파일 생성 시도
  3) 생성/찾아낸 mitmproxy CA(cert) 파일을 CurrentUser/LocalMachine 신뢰 루트에 설치
#>

# 관리자 권한 검사
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "관리자 권한이 필요합니다. 관리자 PowerShell로 실행하세요."
    exit 1
}

# ----- 설정 -----
$ConfDir = Join-Path $env:USERPROFILE ".mitmproxy"
$CACertNames = @("mitmproxy-ca-cert.cer","mitmproxy-ca.pem","mitmproxy-ca.p12")   # 찾을 후보 이름들
$FoundCACert = $null

Write-Host "--- mitmproxy CA 인증서 설치 ---"
Write-Host "[*] mitm proxy confdir: $ConfDir"

# 1) mitm CA 파일이 이미 있는지 확인
Write-Host "[*] CA 파일 확인 중..."
foreach ($name in $CACertNames) {
    $path = Join-Path $ConfDir $name
    if (Test-Path $path) {
        $FoundCACert = $path
        break
    }
}

# 2) CA 파일이 없으면 mitmdump를 잠깐 실행하여 CA 생성 시도
if (-not $FoundCACert) {
    Write-Warning "mitm proxy CA 파일을 찾을 수 없습니다. mitmdump를 잠깐 실행하여 CA를 생성합니다."
    
    # confdir가 없으면 생성
    if (-not (Test-Path $ConfDir)) {
        try { New-Item -ItemType Directory -Path $ConfDir -Force | Out-Null } catch {}
    }

    # mitmdump 실행 (백그라운드). confdir 강제 지정
    $mitmArgs = @("--set", "confdir=$ConfDir")
    try {
        # 'mitmdump'가 PATH에 있다고 가정하고 실행
        $proc = Start-Process -FilePath "mitmdump" -ArgumentList $mitmArgs -WindowStyle Hidden -PassThru -ErrorAction Stop
    } catch {
        Write-Error "mitmdump 실행 실패: $_"
        Write-Host "mitmdump가 PATH에 등록되어 있지 않거나 설치에 문제가 있을 수 있습니다. 수동으로 mitmdump를 실행하세요."
        exit 1
    }

    # 최대 대기: 15초
    $maxWait = 15
    $waited = 0
    while ($waited -lt $maxWait -and -not $FoundCACert) {
        Start-Sleep -Seconds 1
        $waited += 1
        foreach ($name in $CACertNames) {
            $path = Join-Path $ConfDir $name
            if (Test-Path $path) {
                $FoundCACert = $path
                break
            }
        }
        if ($FoundCACert) { break }
    }

    # 프로세스가 남아있다면 종료
    try {
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {}

    if (-not $FoundCACert) {
        Write-Error "자동으로 CA 파일을 생성하지 못했습니다. '%USERPROFILE%\.mitmproxy' 폴더를 수동으로 확인하세요."
        exit 1
    } else {
        Write-Host "[OK] 생성된 CA 파일 발견: $FoundCACert"
    }
} else {
    Write-Host "[OK] 이미 존재하는 CA 파일 발견: $FoundCACert"
}

---

# 3) CA를 신뢰 루트 저장소에 설치 (CurrentUser 및 LocalMachine Root)
Write-Host "[*] CA 인증서를 신뢰 루트 저장소에 설치 중..."

# 설치할 인증서 파일의 확장자 확인 (.cer 또는 .pem 인지)
if ($FoundCACert -like "*.pem") {
    Write-Warning "'.pem' 파일은 'Import-Certificate' 명령이 지원하지 않을 수 있습니다. '.cer' 파일이나 certutil을 사용합니다."
    # .pem 파일인 경우 certutil 사용을 우선 시도
    $InstallCommand = "certutil -addstore Root $FoundCACert"
} else {
    $InstallCommand = "Import-Certificate -FilePath $FoundCACert"
}

try {
    # CurrentUser Root
    Write-Host "  - CurrentUser\Root 에 설치 시도..."
    Import-Certificate -FilePath $FoundCACert -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
    
    # LocalMachine Root (관리자 권한에서만 가능)
    Write-Host "  - LocalMachine\Root 에 설치 시도..."
    Import-Certificate -FilePath $FoundCACert -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
    Write-Host "[OK] 인증서가 CurrentUser 및 LocalMachine 신뢰 루트에 설치되었습니다."
} catch {
    Write-Warning "Import-Certificate 중 오류 발생: $_"
    Write-Host "대안: certutil로 수동 설치 시도"
    try {
        # .pem 이든 .cer 이든 certutil은 보통 잘 처리함
        & certutil -addstore Root $FoundCACert | Out-Null
        Write-Host "[OK] certutil로 루트 저장소에 추가 시도 완료."
    } catch {
        Write-Error "certutil 설치 시도도 실패했습니다: $_"
        Write-Host "수동으로 '%USERPROFILE%\.mitmproxy\$([IO.Path]::GetFileName($FoundCACert))' 파일을 찾아 설치하세요."
        exit 1
    }
}

---

Write-Host ""
Write-Host "=== 완료 ==="
Write-Host "설치된 CA 파일: $FoundCACert"
Write-Host "인증서 관리 MMC (certmgr.msc 또는 certlm.msc)에서 '신뢰할 수 있는 루트 인증 기관'을 확인하세요."
Write-Host ""
Write-Host "인증서 제거 시 (관리자):"
# 인증서 이름을 가져와서 certutil로 삭제하는 명령어 출력
$CertBaseName = ([IO.Path]::GetFileNameWithoutExtension($FoundCACert) -replace 'mitmproxy-ca-cert','mitmproxy')
Write-Host "certutil -delstore Root `"$CertBaseName`""
Write-Host "또는 MMC에서 'Trusted Root Certification Authorities' 에서 수동 삭제 가능합니다."