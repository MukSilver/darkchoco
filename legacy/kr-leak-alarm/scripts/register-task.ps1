<#
.SYNOPSIS
  Kr-Leak-alarm 자동 수집을 Windows 작업 스케줄러에 등록합니다.

.DESCRIPTION
  기본값은 매일 09:00 · 18:00 실행입니다.
  관리자 권한 없이 현재 사용자 계정으로 등록되므로 시스템 권한 상승이 없습니다.
  (SYSTEM 계정으로 돌리지 않는 것이 보안상 더 안전합니다.)

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1
  powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1 -Times "08:00","13:00","20:00"
  powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1 -Remove
#>
param(
  [string[]]$Times = @("09:00","18:00"),
  [string]$TaskName = "Kr-Leak-alarm",
  [switch]$Remove
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if ($Remove) {
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[*] 작업 '$TaskName' 을 제거했습니다."
  } else {
    Write-Host "[*] 등록된 작업이 없습니다."
  }
  return
}

$python = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $python)) {
  Write-Host "[!] .venv 가 없습니다. 먼저 scripts\run.bat 을 한 번 실행하세요." -ForegroundColor Yellow
  return
}

$action   = New-ScheduledTaskAction -Execute $python -Argument "-m collector.main run" -WorkingDirectory $root
$triggers = $Times | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$settings = New-ScheduledTaskSettingsSet `
              -StartWhenAvailable `
              -DontStopOnIdleEnd `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
              -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName `
  -Action $action -Trigger $triggers -Settings $settings `
  -Description "랜섬웨어 DLS 한국 기업 피해 모니터링 (공개 CTI API 전용, Tor 미사용)" `
  -Force | Out-Null

Write-Host "[*] 작업 '$TaskName' 등록 완료 — 실행 시각: $($Times -join ', ')"
Write-Host "[*] 해제하려면: powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1 -Remove"
