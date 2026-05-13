# CryptoJournal - pre-clone bootstrapper for Windows (PowerShell).
#
# Usage:
#   irm https://raw.githubusercontent.com/Grabriel289/trading_journal/main/install.ps1 | iex
#
# Interactive: you'll be asked where to install (default: $HOME\trading_journal).
#
# Env overrides (set before piping; skip prompts):
#   $env:REPO_URL    git clone source (default below)
#   $env:INSTALL_DIR target directory - skips the prompt
#   $env:START       'false' to skip auto-start

$ErrorActionPreference = 'Stop'

$RepoUrl = if ($env:REPO_URL) { $env:REPO_URL } else { 'https://github.com/Grabriel289/trading_journal.git' }
$Start   = if ($env:START)    { $env:START }    else { 'true' }

# Resolve install directory: env var -> interactive prompt -> default.
$DefaultInstallDir = Join-Path $HOME 'trading_journal'
if ($env:INSTALL_DIR) {
    $InstallDir = $env:INSTALL_DIR
} else {
    Write-Host ''
    Write-Host 'Where should CryptoJournal be installed?'
    $userInput = Read-Host "Press Enter to accept [$DefaultInstallDir], or type a path"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $InstallDir = $DefaultInstallDir
    } else {
        # Expand ~ to $HOME and resolve to an absolute path
        $InstallDir = $userInput -replace '^~', $HOME
    }
}

# ASCII-only status prefixes so the script works on non-UTF-8 Windows locales.
function Step($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[X] $m" -ForegroundColor Red; exit 1 }

Write-Host "CryptoJournal install" -ForegroundColor White
Write-Host "  repo:    $RepoUrl"
Write-Host "  target:  $InstallDir"
Write-Host ""

# ---------- prerequisite installer (winget) ----------
function Has-Cmd($name) { $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

# Refresh PATH from the registry - winget installs update the System/User PATH
# in the registry but those changes don't reach the current PowerShell session.
# Call this after every winget install so subsequent commands can find the new
# binaries without requiring the user to restart PowerShell.
function Refresh-Path {
    $machinePath = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
}

function Ensure-Winget {
    if (-not (Has-Cmd 'winget')) {
        Write-Host ''
        Write-Host '[X] winget (Windows Package Manager) is required but not found.' -ForegroundColor Red
        Write-Host ''
        Write-Host 'winget ships with Windows 10 (2021+) and Windows 11. If it''s missing:'
        Write-Host '  1. Open the Microsoft Store'
        Write-Host '  2. Search for "App Installer" and install/update it'
        Write-Host '  3. Re-run this installer'
        Write-Host ''
        Write-Host 'Or download manually from: https://github.com/microsoft/winget-cli/releases'
        Write-Host ''
        exit 1
    }
}

function Install-Winget($id) {
    Ensure-Winget
    winget install --id $id -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
    Refresh-Path
}

# ---------- git ----------
if (-not (Has-Cmd 'git')) {
    Step 'Installing Git'
    Install-Winget 'Git.Git'
    if (-not (Has-Cmd 'git')) { Die 'Git install failed - please install manually from https://git-scm.com/' }
}
Ok ("git " + (git --version).Split()[2])

# ---------- python 3.10+ ----------
# Parse "python --version" output ("Python 3.12.10") instead of running a
# Python one-liner. Avoids PowerShell quote-escaping pitfalls when passing
# embedded Python code to the interpreter on Windows.
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
    if (Has-Cmd $cand) {
        $v = Get-PyMajorMinor $cand
        if ($v -and $v[0] -eq 3 -and $v[1] -ge 10) { $PyBin = $cand; break }
    }
}
if (-not $PyBin) {
    Step 'Installing Python 3.12'
    Install-Winget 'Python.Python.3.12'
    foreach ($cand in 'python3.12','python','python3') {
        if (Has-Cmd $cand) {
            $v = Get-PyMajorMinor $cand
            if ($v -and $v[0] -eq 3 -and $v[1] -ge 10) { $PyBin = $cand; break }
        }
    }
    if (-not $PyBin) {
        Die 'Python install completed but python is still not on PATH. Please restart PowerShell and re-run.'
    }
}
Ok ("$PyBin " + (& $PyBin --version).Split()[1])

# ---------- node 18+ ----------
# Parse "node --version" output ("v22.20.0") instead of node -p "process..." -
# same quote-escaping reason as Python above.
function Get-NodeMajor {
    try {
        $raw = node --version 2>&1
        if ($raw -match 'v(\d+)\.') { return [int]$Matches[1] }
    } catch {}
    return $null
}

$nodeMajor = $null
if (Has-Cmd 'node') { $nodeMajor = Get-NodeMajor }
if (-not $nodeMajor -or $nodeMajor -lt 18) {
    Step 'Installing Node.js LTS'
    Install-Winget 'OpenJS.NodeJS.LTS'
    if (-not (Has-Cmd 'node')) {
        Die 'Node install completed but node is still not on PATH. Please restart PowerShell and re-run.'
    }
}
Ok ("node " + (node --version))

# ---------- clone or pull ----------
if (Test-Path (Join-Path $InstallDir '.git')) {
    Step "Repository already at $InstallDir - pulling latest"
    git -C $InstallDir pull --ff-only | Out-Null
} elseif (Test-Path $InstallDir) {
    Die "$InstallDir exists but is not a git repo. Move it or set `$env:INSTALL_DIR"
} else {
    Step "Cloning $RepoUrl -> $InstallDir"
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
