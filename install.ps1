# CryptoJournal — pre-clone bootstrapper for Windows (PowerShell).
#
# Usage:
#   irm https://raw.githubusercontent.com/Grabriel289/trading_journal/main/install.ps1 | iex
#
# Env overrides (set before piping):
#   $env:REPO_URL    git clone source (default below)
#   $env:INSTALL_DIR target directory (default $HOME\crypto_journal)
#   $env:START       'false' to skip auto-start

$ErrorActionPreference = 'Stop'

$RepoUrl    = if ($env:REPO_URL)    { $env:REPO_URL }    else { 'https://github.com/Grabriel289/trading_journal.git' }
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $HOME 'crypto_journal' }
$Start      = if ($env:START)       { $env:START }       else { 'true' }

function Step($m) { Write-Host "→ $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "✔ $m" -ForegroundColor Green }
function Warn($m) { Write-Host "! $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "✖ $m" -ForegroundColor Red; exit 1 }

Write-Host "CryptoJournal install" -ForegroundColor White
Write-Host "  repo:    $RepoUrl"
Write-Host "  target:  $InstallDir"
Write-Host ""

# ---------- prerequisite installer (winget) ----------
function Has-Cmd($name) { $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

function Ensure-Winget {
    if (-not (Has-Cmd 'winget')) {
        Die "winget not found. Update Windows or install 'App Installer' from the Microsoft Store."
    }
}

function Install-Winget($id) {
    Ensure-Winget
    winget install --id $id -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
}

# ---------- git ----------
if (-not (Has-Cmd 'git')) {
    Step 'Installing Git'
    Install-Winget 'Git.Git'
    $env:Path += ";C:\Program Files\Git\cmd"
}
Ok ("git " + (git --version).Split()[2])

# ---------- python 3.10+ ----------
$PyBin = $null
foreach ($cand in 'python3.12','python3.11','python3.10','python','python3') {
    if (Has-Cmd $cand) {
        try {
            $v = & $cand -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")'
            $major,$minor = $v.Split('.')
            if ([int]$major -eq 3 -and [int]$minor -ge 10) { $PyBin = $cand; break }
        } catch {}
    }
}
if (-not $PyBin) {
    Step 'Installing Python 3.12'
    Install-Winget 'Python.Python.3.12'
    foreach ($cand in 'python3.12','python','python3') {
        if (Has-Cmd $cand) { $PyBin = $cand; break }
    }
    if (-not $PyBin) { Die 'Python install failed' }
}
Ok ("$PyBin " + (& $PyBin --version).Split()[1])

# ---------- node 18+ ----------
$needNode = $true
if (Has-Cmd 'node') {
    $major = [int]((node -p 'process.versions.node.split(".")[0]'))
    if ($major -ge 18) { $needNode = $false }
}
if ($needNode) {
    Step 'Installing Node.js LTS'
    Install-Winget 'OpenJS.NodeJS.LTS'
}
Ok ("node " + (node --version))

# ---------- clone or pull ----------
if (Test-Path (Join-Path $InstallDir '.git')) {
    Step "Repository already at $InstallDir — pulling latest"
    git -C $InstallDir pull --ff-only | Out-Null
} elseif (Test-Path $InstallDir) {
    Die "$InstallDir exists but is not a git repo. Move it or set `$env:INSTALL_DIR"
} else {
    Step "Cloning $RepoUrl → $InstallDir"
    git clone --depth 1 $RepoUrl $InstallDir
}

# ---------- install deps + (optionally) run ----------
Set-Location $InstallDir
if ($Start -eq 'true') {
    Step 'Bootstrapping deps + starting servers'
    powershell -ExecutionPolicy Bypass -File .\dev.ps1
} else {
    Step 'Installing deps only'
    powershell -ExecutionPolicy Bypass -File .\dev.ps1 -InstallOnly
    Write-Host ''
    Ok 'Done. Start the app with:'
    Write-Host "    cd $InstallDir; .\dev.ps1"
}
