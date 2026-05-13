# CryptoJournal - Windows native dev runner (mirror of dev.sh).
#
#   .\dev.ps1                  # install (if needed) + start backend + frontend
#   .\dev.ps1 -InstallOnly     # set up deps, don't start
#   .\dev.ps1 -Reset           # wipe .venv, node_modules, SQLite db

param(
    [switch]$InstallOnly,
    [switch]$Reset
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# ASCII-only status prefixes so the script works on non-UTF-8 Windows locales
# (Thai, Vietnamese, etc.) where PowerShell 5 reads files in the OEM codepage
# and corrupts Unicode glyphs like the heavy check mark or arrows.
function Step($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Die($m)  { Write-Host "[X] $m" -ForegroundColor Red; exit 1 }

if ($Reset) {
    Step 'Wiping .venv, frontend\node_modules, data\cryptojournal.db'
    Remove-Item -Recurse -Force .venv,frontend\node_modules,frontend\dist,data\cryptojournal.db -ErrorAction SilentlyContinue
    exit 0
}

# ---------- toolchain detection ----------
# Parse "python --version" output instead of running an embedded Python script.
# Avoids PowerShell quote-escaping issues with the inner f-string.
function Get-PyMajorMinor($cand) {
    try {
        $raw = & $cand --version 2>&1
        if ($raw -match 'Python (\d+)\.(\d+)') {
            return @([int]$Matches[1], [int]$Matches[2])
        }
    } catch {}
    return $null
}

$PyBin = $null
foreach ($cand in 'python3.12','python3.11','python3.10','python','python3') {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        $v = Get-PyMajorMinor $cand
        if ($v -and $v[0] -eq 3 -and $v[1] -ge 10) { $PyBin = $cand; break }
    }
}
if (-not $PyBin) { Die 'Python 3.10+ not found. Install Python 3.12 and re-run.' }

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Die 'Node.js not found. Install Node 18+.' }

# Parse "node --version" ("v22.20.0") instead of node -p with embedded JS.
$nodeRaw = node --version 2>&1
if ($nodeRaw -notmatch 'v(\d+)\.') { Die 'Could not parse node version.' }
if ([int]$Matches[1] -lt 18) { Die 'Node 18+ required.' }

# ---------- backend deps ----------
$venvPy  = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$venvPip = Join-Path $PSScriptRoot '.venv\Scripts\pip.exe'

if (-not (Test-Path .venv)) {
    Step "Creating Python venv ($PyBin)"
    & $PyBin -m venv .venv
}

$reqHashFile = '.venv\.requirements.hash'
$reqHash = (Get-FileHash requirements.txt -Algorithm SHA1).Hash
$existing = if (Test-Path $reqHashFile) { Get-Content $reqHashFile } else { '' }
if ($existing -ne $reqHash) {
    Step 'Installing Python dependencies'
    # On Windows, pip cannot upgrade itself via pip.exe because the binary
    # holds itself open. Use `python -m pip` instead so pip is loaded into
    # the Python process and the .exe file is free to be replaced.
    & $venvPy -m pip install --quiet --upgrade pip
    & $venvPy -m pip install --quiet -r requirements.txt
    Set-Content -Path $reqHashFile -Value $reqHash
}

# ---------- frontend deps ----------
$pkgHashFile = 'frontend\node_modules\.package.hash'
$pkgHash = (Get-FileHash frontend\package.json -Algorithm SHA1).Hash
$pkgExisting = if (Test-Path $pkgHashFile) { Get-Content $pkgHashFile } else { '' }
if (-not (Test-Path 'frontend\node_modules') -or $pkgExisting -ne $pkgHash) {
    Step 'Installing frontend dependencies'
    Push-Location frontend
    npm install --silent
    Pop-Location
    Set-Content -Path $pkgHashFile -Value $pkgHash
}

if ($InstallOnly) {
    Ok 'Install complete. Run .\dev.ps1 to start the app.'
    exit 0
}

# ---------- run ----------
$BackendPort  = if ($env:BACKEND_PORT)  { $env:BACKEND_PORT }  else { 8000 }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { 5173 }

function PortInUse($port) {
    return (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) -ne $null
}
if (PortInUse $BackendPort)  { Die "port $BackendPort already in use." }
if (PortInUse $FrontendPort) { Die "port $FrontendPort already in use." }

# Apply Alembic migrations, with self-heal for half-built DBs from older
# broken installs that stamped alembic_version with a now-deleted revision.
# Notes for PowerShell 5: `& cmd 2>&1 | Out-String` under
# $ErrorActionPreference = 'Stop' can throw on stderr text before we ever
# reach the $LASTEXITCODE check. We avoid capturing stderr - just let
# alembic print to console and read the exit code directly.
Step 'Applying schema migrations (alembic upgrade head)'
$prevPref = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $venvPy -m alembic upgrade head
$migrationExit = $LASTEXITCODE
$ErrorActionPreference = $prevPref

if ($migrationExit -ne 0) {
    Write-Host ''
    Write-Host '[!] Migration failed. Most likely a half-built DB from an earlier' -ForegroundColor Yellow
    Write-Host '    failed install. Wiping data\cryptojournal.db and retrying...' -ForegroundColor Yellow
    Remove-Item -Force data\cryptojournal.db -ErrorAction SilentlyContinue
    $ErrorActionPreference = 'Continue'
    & $venvPy -m alembic upgrade head
    $migrationExit = $LASTEXITCODE
    $ErrorActionPreference = $prevPref
    if ($migrationExit -ne 0) { Die 'Migration still failing - see error above.' }
}

Step "Starting backend on http://localhost:$BackendPort"
$backend = Start-Process -FilePath $venvPy `
    -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',$BackendPort,'--reload' `
    -PassThru -NoNewWindow

# Wait for /api/health
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
        break
    } catch { Start-Sleep -Milliseconds 500 }
}

# Cleanup hook
$cleanup = {
    if ($backend -and -not $backend.HasExited) {
        Write-Host "[*] Stopping backend (pid $($backend.Id))" -ForegroundColor Cyan
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
Register-EngineEvent PowerShell.Exiting -Action $cleanup | Out-Null

$projectDir = $PSScriptRoot
@"

==================================================
 CryptoJournal is running
   Frontend: http://localhost:$FrontendPort
   Backend:  http://localhost:$BackendPort/docs
   Stop:     Ctrl+C

 To restart later, in a new PowerShell window:
   cd $projectDir; .\dev.ps1
==================================================

"@ | Write-Host

# Auto-open the dashboard in the default browser once Vite is likely ready.
# Set `$env:NO_BROWSER='1' to disable (useful over SSH / CI).
if ($env:NO_BROWSER -ne '1') {
    Start-Job -ScriptBlock {
        param($u)
        Start-Sleep -Seconds 4
        Start-Process $u
    } -ArgumentList "http://localhost:$FrontendPort" | Out-Null
}

try {
    Push-Location frontend
    npm run dev
} finally {
    Pop-Location
    & $cleanup
}
