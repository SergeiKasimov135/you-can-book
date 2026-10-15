# Запуск ЛР1: Docker -> .env -> PostgreSQL -> миграции, тестовые данные, демо
#   .\setup.ps1            Python из .venv, при ошибке подключения — внутри Docker
#   .\setup.ps1 -InDocker  сразу внутри Docker
#   .\setup.ps1 -SkipDemo  без демо
param(
    [switch]$InDocker,
    [switch]$SkipDemo
)

# Не 'Stop': PowerShell 5.1 считает stderr ошибкой, проверяем $LASTEXITCODE
$ErrorActionPreference = 'Continue'
Set-Location -Path $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$ContainerName = 'you-can-book-postgres'
$ApiDir = Join-Path $PSScriptRoot 'api-service'
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "    $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "    $Text" -ForegroundColor Yellow }
function Stop-WithError([string]$Text) {
    Write-Host "`nОШИБКА: $Text" -ForegroundColor Red
    exit 1
}

function Wait-PostgresHealthy([int]$TimeoutSec = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $status = (docker inspect --format '{{.State.Health.Status}}' $ContainerName 2>$null)
        if ($status -eq 'healthy') { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Get-EnvPort([string]$Path) {
    $port = 5432
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match '^\s*POSTGRES_PORT\s*=\s*(\d+)\s*$') { $port = [int]$Matches[1] }
    }
    return $port
}

function Sync-ApiEnv([string]$Path, [int]$Port) {
    # Приводим DATABASE_URL к виду ...@127.0.0.1:<порт>/...?ssl=disable
    $text = [System.IO.File]::ReadAllText($Path)
    $new = [regex]::Replace($text, '@(localhost|127\.0\.0\.1):\d+/', "@127.0.0.1:$Port/")
    $new = [regex]::Replace($new, '(?m)^(DATABASE_URL=[^\r\n?]+)(\r?)$', '$1?ssl=disable$2')
    if ($new -ne $text) {
        [System.IO.File]::WriteAllText($Path, $new, $Utf8NoBom)
        Write-Ok "api-service\.env: DATABASE_URL переведён на 127.0.0.1:$Port"
    }
}

function Invoke-InDocker {
    Write-Step 'Запуск кода внутри Docker (сеть you-can-book-network)'
    docker compose build api
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Не удалось собрать образ api (docker compose build api). Если VPN блокирует PyPI, сборка не пройдёт.' }

    $steps = @(
        @{ Title = 'Миграции: alembic upgrade head'; Cmd = @('alembic', 'upgrade', 'head') },
        @{ Title = 'Тестовые данные: scripts.seed'; Cmd = @('python', '-m', 'scripts.seed') }
    )
    if (-not $SkipDemo) {
        $steps += @{ Title = 'Демонстрация: scripts.demo'; Cmd = @('python', '-m', 'scripts.demo') }
    }
    foreach ($s in $steps) {
        Write-Step $s.Title
        $cmd = $s.Cmd
        docker compose run --rm api @cmd
        if ($LASTEXITCODE -ne 0) { Stop-WithError "Шаг «$($s.Title)» завершился с ошибкой" }
    }
}

# Результат в $script:LocalOk: return в PowerShell захватил бы весь вывод
$script:LocalOk = $false

function Invoke-Local([int]$Port) {
    Write-Step 'Python-окружение (.venv)'
    $py = Join-Path $ApiDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $py)) {
        $sysPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $sysPython) { Stop-WithError 'Python не найден. Установи Python 3.11+ с галочкой "Add python.exe to PATH" или запусти скрипт с -InDocker' }
        python -m venv (Join-Path $ApiDir '.venv')
        if ($LASTEXITCODE -ne 0) { Stop-WithError 'Не удалось создать .venv' }
        Write-Ok '.venv создан'
    }
    & $py -m pip install --disable-pip-version-check -q -r (Join-Path $ApiDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'pip install завершился с ошибкой' }
    Write-Ok 'Зависимости установлены'

    Write-Step "Проверка подключения к 127.0.0.1:$Port"
    $tcpOk = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
    if (-not $tcpOk) {
        Write-Warn "Порт $Port на 127.0.0.1 недоступен"
        return
    }

    Push-Location $ApiDir
    try {
        Write-Step 'Миграции: alembic upgrade head'
        & $py -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            Write-Warn 'Alembic не смог подключиться к БД с Windows (часто причина — VPN)'
            return
        }
        & $py -m alembic current

        Write-Step 'Тестовые данные: scripts.seed'
        & $py -m scripts.seed
        if ($LASTEXITCODE -ne 0) { Stop-WithError 'scripts.seed завершился с ошибкой' }

        if (-not $SkipDemo) {
            Write-Step 'Демонстрация: scripts.demo'
            & $py -m scripts.demo
            if ($LASTEXITCODE -ne 0) { Stop-WithError 'scripts.demo завершился с ошибкой' }
        }
        $script:LocalOk = $true
    }
    finally {
        Pop-Location
    }
}

# ------------------------------------------------------------------ 1. Docker
Write-Step 'Проверка Docker'
docker info *> $null
if ($LASTEXITCODE -ne 0) { Stop-WithError 'Docker Desktop не запущен. Запусти его и дождись статуса "Engine running".' }
Write-Ok 'Docker запущен'

# ------------------------------------------------------------------ 2. .env
Write-Step 'Файлы настроек .env'
foreach ($dir in @($PSScriptRoot, $ApiDir)) {
    $envFile = Join-Path $dir '.env'
    if (-not (Test-Path $envFile)) {
        Copy-Item (Join-Path $dir '.env.example') $envFile
        Write-Ok "Создан $envFile"
    }
}
$port = Get-EnvPort (Join-Path $PSScriptRoot '.env')
Write-Ok "Порт PostgreSQL на компьютере: $port (POSTGRES_PORT в корневом .env)"
Sync-ApiEnv (Join-Path $ApiDir '.env') $port

# ------------------------------------------------------------------ 3. PostgreSQL
Write-Step 'Запуск PostgreSQL в Docker'
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) { Stop-WithError 'docker compose up завершился с ошибкой. Если порт занят — поменяй POSTGRES_PORT в корневом .env' }

# Если контейнер был создан со старым портом — пересоздаём
$mapping = (docker compose port postgres 5432 2>$null | Select-Object -First 1)
if ($mapping -notmatch ":$port$") {
    Write-Warn "Контейнер опубликован на '$mapping', а нужен порт $port — пересоздаю"
    docker compose up -d --force-recreate postgres
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Не удалось пересоздать контейнер' }
}

Write-Ok 'Жду готовности базы...'
if (-not (Wait-PostgresHealthy)) {
    docker compose logs postgres --tail 30
    Stop-WithError 'PostgreSQL не стал healthy за 90 секунд (логи выше)'
}
Write-Ok "PostgreSQL готов: $(docker compose port postgres 5432)"

# ------------------------------------------------------------------ 4. Код
if ($InDocker) {
    Invoke-InDocker
}
else {
    Invoke-Local -Port $port
    if (-not $script:LocalOk) {
        Write-Warn 'Переключаюсь на запуск внутри Docker — там VPN и сеть Windows не мешают'
        Invoke-InDocker
    }
}

Write-Host "`nГотово. База: 127.0.0.1:$port, БД you_can_book_db, пользователь you_can_book" -ForegroundColor Green
