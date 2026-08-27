param(
    [switch]$TestRun,
    [switch]$Install,
    [switch]$Run
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "WHS-Telegram-Monitor"

function Import-UserEnvironment {
    $required = @("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "NOTION_TOKEN")
    foreach ($name in $required) {
        $value = [Environment]::GetEnvironmentVariable($name, "User")
        if ([string]::IsNullOrWhiteSpace($value)) {
            throw "Missing user environment variable: $name"
        }
        Set-Item -Path "Env:$name" -Value $value
    }
}

function Invoke-TelegramMonitor {
    param([bool]$ApplyNotion)

    Import-UserEnvironment
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python was not found in PATH."
    }
    $pythonPath = $pythonCommand.Source
    Set-Location $ProjectDir
    $arguments = @(".\monitor_channels.py")
    if ($ApplyNotion) {
        $arguments += "--apply-notion"
    }
    & $pythonPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Telegram monitoring failed with exit code $LASTEXITCODE."
    }
}

if ($TestRun) {
    Write-Host "Test run: Notion preview mode"
    Invoke-TelegramMonitor -ApplyNotion $false
    exit 0
}

if ($Run) {
    Invoke-TelegramMonitor -ApplyNotion $true
    exit 0
}

if ($Install) {
    Import-UserEnvironment
    $scriptPath = $MyInvocation.MyCommand.Path
    $shellPath = (Get-Process -Id $PID).Path
    $actionArguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $scriptPath + '" -Run'

    $actionParams = @{
        Execute = $shellPath
        Argument = $actionArguments
        WorkingDirectory = $ProjectDir
    }
    $action = New-ScheduledTaskAction @actionParams
    $triggers = @(
        (New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(9)))
        (New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(18)))
    )
    $settingsParams = @{
        StartWhenAvailable = $true
        AllowStartIfOnBatteries = $true
        DontStopIfGoingOnBatteries = $true
        MultipleInstances = "IgnoreNew"
        ExecutionTimeLimit = (New-TimeSpan -Hours 1)
    }
    $settings = New-ScheduledTaskSettingsSet @settingsParams
    $userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $registerParams = @{
        TaskName = $TaskName
        Action = $action
        Trigger = $triggers
        Settings = $settings
        User = $userId
        RunLevel = "Limited"
        Description = "WHS Telegram monitor: 09:00 and 18:00"
        Force = $true
    }
    Register-ScheduledTask @registerParams | Out-Null
    Write-Host "Scheduled task installed: $TaskName"
    Write-Host "Daily run times: 09:00 and 18:00"
    Write-Host "The PC must be on and the Windows user must be signed in."
    exit 0
}

Write-Host "Usage:"
Write-Host "  Test:    .\telegram_schedule.ps1 -TestRun"
Write-Host "  Install: .\telegram_schedule.ps1 -Install"
