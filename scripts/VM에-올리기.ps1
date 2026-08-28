# VirtualBox VM 에 저장소를 넣고 자리를 만듭니다. 윈도우에서 돌립니다.
#
#     powershell -File scripts\VM에-올리기.ps1
#     powershell -File scripts\VM에-올리기.ps1 -Vm "이름" -User kali
#
# 왜 VM 인가 — Tor 는 저쪽이 우리 IP 를 보는 것을 막고, VM 은 그 쪽
# 페이지가 우리 기기로 내려오는 것을 막습니다. 서로 대체가 안 됩니다.
# 윈도우에서 그냥 돌리면 다크웹 쪽이 이 PC 로 내려오고 V3 가 막습니다.
#
# 하는 일
#   1. VM 을 켭니다 (창 없이)
#   2. Guest Additions 가 올라오기를 기다립니다
#   3. 호스트와 이어진 길(공유 폴더·클립보드·드래그)을 끊습니다
#   4. 저장소를 넣습니다 (.git · .venv 는 뺍니다)
#   5. 안에서 돌릴자리-만들기.sh 를 돌립니다
#   6. 노션 토큰을 넣습니다 (있으면)
#   7. 점검합니다
#
# **비밀번호는 파일로 넘기고 바로 지웁니다.** 명령줄에 두면 프로세스
# 목록에 보입니다.

param(
    [string]$Vm       = "kali-linux-2026.2-virtualbox-amd64",
    [string]$User     = "kali",
    [string]$Password = "kali",
    [string]$Repo     = "",
    [string]$TokenFile = "$env:USERPROFILE\.config\darkchoco\notion_token.txt",
    [switch]$SkipToken
)

$ErrorActionPreference = "Stop"

# 콘솔이 UTF-8 이어야 한글이 안 깨집니다.
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

# **윈도우 기본 tar 를 씁니다.** 이름을 TarExe 로 둡니다 —
# PowerShell 은 변수 이름의 대소문자를 안 가려서 $Tar 로 두면
# 아래의 묶음 파일 $tar 와 같은 변수가 됩니다. PATH 앞쪽에 git-bash 의 tar 가 있으면
# "C:\..." 를 원격 호스트로 읽습니다.
#   /usr/bin/tar: Cannot connect to C: resolve failed
$TarExe = "$env:SystemRoot/System32/tar.exe"
if (-not (Test-Path $TarExe)) { $TarExe = "tar" }
$VBox = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
if (-not (Test-Path $VBox)) { throw "VBoxManage 를 못 찾습니다: $VBox" }
if (-not $Repo) { $Repo = Split-Path -Parent $PSScriptRoot }

function Step($m) { Write-Host "`n$m" -ForegroundColor White }
function OK($m)   { Write-Host "  OK $m" -ForegroundColor Green }
function Bad($m)  { Write-Host "  !! $m" -ForegroundColor Red }
function Say($m)  { Write-Host "     $m" }

# 비밀번호 파일. 끝나면 지웁니다.
$PwFile = Join-Path $env:TEMP ("vbgc-" + [guid]::NewGuid().ToString("N") + ".txt")
$Password | Out-File -LiteralPath $PwFile -Encoding ascii -NoNewline

function VmRun([string]$Cmd, [switch]$Quiet) {
    $out = & $VBox guestcontrol $Vm --username $User --passwordfile $PwFile `
           run --wait-stdout --wait-stderr -- /bin/bash -lc $Cmd 2>&1
    if (-not $Quiet) { $out }
    else { $out | Out-Null }
    return $LASTEXITCODE
}

try {
    # ── 1. 켭니다 ──────────────────────────────────────────────────
    Step "1. VM 켜기"
    $state = (& $VBox showvminfo $Vm --machinereadable 2>$null |
              Select-String '^VMState=').Line
    if ($state -match 'running') {
        OK "이미 돌고 있습니다"
    } else {
        & $VBox startvm $Vm --type headless | Out-Null
        OK "켰습니다 (창 없이)"
    }

    # ── 2. Guest Additions ─────────────────────────────────────────
    Step "2. Guest Additions 기다리기"
    Say "이것이 있어야 밖에서 VM 안의 명령을 돌릴 수 있습니다."
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 10
        $lvl = (& $VBox showvminfo $Vm --machinereadable 2>$null |
                Select-String '^GuestAdditionsRunLevel=').Line
        if ($lvl -and $lvl -notmatch '=0') { $ready = $true; break }
        if ($i % 3 -eq 2) { Say "부팅 중... ($(($i+1)*10)초)" }
    }
    if (-not $ready) {
        Bad "Guest Additions 가 안 올라옵니다."
        Say "VM 안에서 깔아야 합니다:"
        Say "  sudo apt install -y virtualbox-guest-x11 && sudo reboot"
        exit 1
    }
    $ver = (& $VBox showvminfo $Vm --machinereadable 2>$null |
            Select-String '^GuestAdditionsVersion=').Line
    OK "돕니다 — $ver"

    # ── 3. 호스트와 이어진 길 끊기 ─────────────────────────────────
    Step "3. 호스트와 이어진 길 끊기"
    Say "켜 두면 오염이 윈도우로 건너옵니다."
    & $VBox controlvm $Vm clipboard mode disabled 2>&1 | Out-Null
    & $VBox controlvm $Vm draganddrop disabled 2>&1 | Out-Null
    OK "클립보드 · 드래그 앤 드롭 껐습니다"
    $shares = & $VBox showvminfo $Vm --machinereadable 2>$null |
              Select-String '^SharedFolderNameMachineMapping'
    if ($shares) {
        Bad "공유 폴더가 있습니다. 손으로 지우십시오:"
        $shares | ForEach-Object { Say $_.Line }
    } else {
        OK "공유 폴더 없습니다"
    }

    # ── 4. 저장소 넣기 ─────────────────────────────────────────────
    Step "4. 저장소 넣기"
    $tar = Join-Path $env:TEMP ("darkchoco-" + [guid]::NewGuid().ToString("N") + ".tar")
    Push-Location $Repo
    & $TarExe --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude=*.pyc -cf $tar .
    Pop-Location
    $mb = [math]::Round((Get-Item $tar).Length / 1MB, 1)
    & $VBox guestcontrol $Vm --username $User --passwordfile $PwFile `
        copyto --target-directory "/home/$User/" $tar | Out-Null
    $base = Split-Path -Leaf $tar
    VmRun "rm -rf ~/darkchoco && mkdir -p ~/darkchoco && tar -xf ~/$base -C ~/darkchoco && rm -f ~/$base" -Quiet | Out-Null
    Remove-Item -LiteralPath $tar -Force -ErrorAction SilentlyContinue
    $n = (VmRun 'find ~/darkchoco -type f | wc -l') -join ""
    OK "$mb MB · 파일 $($n.Trim())개 (.git 과 .venv 는 안 넣습니다)"

    # ── 5. 자리 만들기 ─────────────────────────────────────────────
    Step "5. VM 안에서 자리 만들기"
    Say "tor 설치 · torrc · 띄우기 · 나가 보기 · 부품. 몇 분 걸립니다."
    $setup = "cd ~/darkchoco && echo '$Password' | sudo -S -v 2>/dev/null && " +
             'bash scripts/돌릴자리-만들기.sh 2>&1 | sed "s/\x1b\[[0-9;]*m//g"'
    VmRun $setup

    # ── 6. 노션 토큰 ───────────────────────────────────────────────
    Step "6. 노션 토큰"
    if ($SkipToken) {
        Say "건너뜁니다 (-SkipToken)"
    } elseif (Test-Path $TokenFile) {
        & $VBox guestcontrol $Vm --username $User --passwordfile $PwFile `
            run --wait-stdout -- /bin/bash -lc "mkdir -p ~/.config/darkchoco" | Out-Null
        & $VBox guestcontrol $Vm --username $User --passwordfile $PwFile `
            copyto --target-directory "/home/$User/.config/darkchoco/" $TokenFile | Out-Null
        VmRun "chmod 600 ~/.config/darkchoco/notion_token.txt" -Quiet | Out-Null
        OK "넣었습니다 (VM 안에만 둡니다)"
    } else {
        Bad "토큰 파일이 없습니다: $TokenFile"
        Say "노션에 못 씁니다. 읽기만 됩니다."
    }

    # ── 7. 점검 ────────────────────────────────────────────────────
    Step "7. 점검"
    VmRun 'cd ~/darkchoco && ./.venv/bin/python dc.py doctor --net 2>&1 | sed -n "/밖으로 나가는 길/,\$p"'

    Step "다 됐습니다"
    Say "VM 안에서 돌리려면"
    Say "  powershell -File scripts\VM에서-돌리기.ps1 'crawl --limit 3'"
    Say "  powershell -File scripts\VM에서-돌리기.ps1 'crawl --apply'"
    Say ""
    Say "코드를 고친 뒤 다시 넣으려면 -Sync 를 주십시오."
    Write-Host ""
}
finally {
    Remove-Item -LiteralPath $PwFile -Force -ErrorAction SilentlyContinue
}
