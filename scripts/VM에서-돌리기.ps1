# VM 안에서 dc.py 를 돌립니다. 윈도우에서 부릅니다.
#
#     powershell -File scripts\VM에서-돌리기.ps1 "doctor --net"
#     powershell -File scripts\VM에서-돌리기.ps1 "crawl --limit 3"
#     powershell -File scripts\VM에서-돌리기.ps1 "crawl --apply"
#     powershell -File scripts\VM에서-돌리기.ps1 "auto"
#
# 저장소를 다시 넣으려면 -Sync 를 주십시오. 윈도우에서 코드를 고친 뒤에
# 씁니다.
#
#     powershell -File scripts\VM에서-돌리기.ps1 -Sync "crawl --limit 3"
#
# **VM 이 꺼져 있으면 켭니다.** Guest Additions 를 기다립니다.
# 자리가 아직 없으면 VM에-올리기.ps1 을 먼저 돌리십시오.

param(
    [Parameter(Position = 0)]
    [string]$Args_    = "doctor --net",
    [string]$Vm       = "kali-linux-2026.2-virtualbox-amd64",
    [string]$User     = "kali",
    [string]$Password = "kali",
    [int]$Port     = 9080,
    [string]$Repo     = "",
    [switch]$Sync,
    # 끝나면 VM 을 재웁니다. 2GB 를 계속 물고 있을 이유가 없습니다.
    # savestate 는 지금 상태를 저장하므로 다음에 켤 때 부팅을 안 합니다
    # (tor 도 그대로 살아 있습니다).
    [switch]$Sleep_
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

function Say($m) { Write-Host "  $m" }

$PwFile = Join-Path $env:TEMP ("vbgc-" + [guid]::NewGuid().ToString("N") + ".txt")
$Password | Out-File -LiteralPath $PwFile -Encoding ascii -NoNewline

# 밖에서 부르는 셸은 ~/.bashrc 를 안 읽습니다. bash -lc 는 로그인 셸이라
# ~/.profile 을 읽는데, 데비안 계열 .bashrc 는 비대화형이면 맨 앞에서
# 빠져나갑니다. 그래서 자리 만들기가 넣어 둔 TOR_SOCKS_PROXY 가 여기서는
# 안 보입니다. 명령에 직접 실어 줍니다.
$EnvPrefix = "export TOR_SOCKS_PROXY=http://127.0.0.1:$Port PYTHONIOENCODING=utf-8; "

function VmRun([string]$Cmd) {
    & $VBox guestcontrol $Vm --username $User --passwordfile $PwFile `
        run --wait-stdout --wait-stderr -- /bin/bash -lc ($EnvPrefix + $Cmd) 2>&1
}

try {
    # VM 이 꺼져 있으면 켭니다.
    $state = (& $VBox showvminfo $Vm --machinereadable 2>$null |
              Select-String '^VMState=').Line
    $WeStartedIt = $false
    if ($state -notmatch 'running') {
        Say "VM 을 켭니다... (창 없이)"
        & $VBox startvm $Vm --type headless | Out-Null
        $WeStartedIt = $true
    }
    for ($i = 0; $i -lt 30; $i++) {
        $lvl = (& $VBox showvminfo $Vm --machinereadable 2>$null |
                Select-String '^GuestAdditionsRunLevel=').Line
        if ($lvl -and $lvl -notmatch '=0') { break }
        Start-Sleep -Seconds 10
    }

    if ($Sync) {
        Say "저장소를 다시 넣습니다..."
        $tar = Join-Path $env:TEMP ("dc-" + [guid]::NewGuid().ToString("N") + ".tar")
        Push-Location $Repo
        & $TarExe --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude=*.pyc -cf $tar .
        Pop-Location
        & $VBox guestcontrol $Vm --username $User --passwordfile $PwFile `
            copyto --target-directory "/home/$User/" $tar | Out-Null
        $base = Split-Path -Leaf $tar
        # .venv 는 남깁니다. 다시 깔면 오래 걸립니다.
        VmRun "cd ~/darkchoco && tar -xf ~/$base && rm -f ~/$base" | Out-Null
        Remove-Item -LiteralPath $tar -Force -ErrorAction SilentlyContinue
        Say "넣었습니다"
    }

    # tor 가 떠 있는지 봅니다. 없으면 크롤러가 스스로 안 나가지만,
    # 여기서 먼저 알려 주는 편이 낫습니다.
    $up = (VmRun 'ss -ltn 2>/dev/null | grep -c ":9080" || echo 0') -join ""
    if ($up.Trim() -eq "0") {
        Say "tor 가 안 떠 있습니다. 띄웁니다..."
        VmRun "echo '$Password' | sudo -S systemctl start tor 2>/dev/null; sleep 5" | Out-Null
    }

    # 이 판에 우리가 켰나. 우리가 켰을 때만 재웁니다 — 김무근 님이
    # 쓰고 계신 VM 을 마음대로 끄면 안 됩니다.
    $py = './.venv/bin/python'
    $cmd = "cd ~/darkchoco && [ -x $py ] || py=python3; " +
           "{ [ -x $py ] && $py dc.py $Args_ || python3 dc.py $Args_ ; } 2>&1"
    VmRun $cmd
}
finally {
    Remove-Item -LiteralPath $PwFile -Force -ErrorAction SilentlyContinue
    if ($Sleep_ -and $WeStartedIt) {
        Say ""
        Say "VM 을 재웁니다 (savestate). 다음에 켤 때 부팅을 안 합니다."
        & $VBox controlvm $Vm savestate 2>&1 | Out-Null
    }
}
