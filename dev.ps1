# CryptoJournal — Windows native dev runner (mirror of dev.sh).
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

function Step($m) { Write-Host "→ $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "✔ $m" -ForegroundColor Green }
function Die($m)  { Write-Host "✖ $m" -ForegroundColor Red; exit 1 }

if ($Reset) {
    Step 'Wiping .venv, frontend\node_modules, data\cryptojournal.db'
    Remove-Item -Recurse -Force .venv,frontend\node_modules,frontend\dist,data\cryptojournal.db -ErrorAction SilentlyContinue
    exit 0
}

# ---------- toolchain detection ----------
$PyBin = $null
foreach ($cand in 'python3.12','python3.11','python3.10','python','python3') {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        try {
            $v = & $cand -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")'
            $maj,$min = $v.Split('.')
            if ([int]$maj -eq 3 -and [int]$min -ge 10) { $PyBin = $cand; break }
        } catch {}
    }
}
if (-not $PyBin) { Die 'Python 3.10+ not found. Install Python 3.12 and re-run.' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Die 'Node.js not found. Install Node 18+.' }
if ([int]((node -p 'process.versions.node.split(".")[0]')) -lt 18) { Die 'Node 18+ required.' }

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
    & $venvPip install --quiet --upgrade pip
    & $venvPip install --quiet -r requirements.txt
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
        Write-Host "→ Stopping backend (pid $($backend.Id))" -ForegroundColor Cyan
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
Register-EngineEvent PowerShell.Exiting -Action $cleanup | Out-Null

@"

==================================================
 CryptoJournal is running
   Frontend: http://localhost:$FrontendPort
   Backend:  http://localhost:$BackendPort/docs
   Stop:     Ctrl+C
==================================================

"@ | Write-Host

# Auto-open the dashboard in the default browser once Vite is likely ready.
# Set $env:NO_BROWSER='1' to disable (useful over SSH / CI).
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
