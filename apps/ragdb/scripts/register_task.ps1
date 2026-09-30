# 배치를 윈도우 작업 스케줄러에 건다 (설계서 2.4: 주 1회와 손으로).
#
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1            걸기 (월요일 04:00)
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -Remove    지우기
#
# 배치는 로그인한 사람의 계정으로 돈다. 질의 서버 계정과 다른 계정이다 (SR-21, SR-22).
# 실패하면 refresh.py 가 디스코드로 알린다. 성공은 알리지 않는다.
param(
    [switch]$Remove,
    [string]$Day = "Monday",
    [string]$At = "04:00"
)

$ErrorActionPreference = "Stop"
$name = "darkchoco-ragdb-refresh"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\refresh.py"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    "지웠습니다: $name"
    return
}
if (-not (Test-Path $python)) { throw ".venv 가 없습니다. README 의 「돌리기」 를 먼저 하십시오" }

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
"걸었습니다: $name ($Day $At). 손으로 돌리려면 Start-ScheduledTask -TaskName $name"
