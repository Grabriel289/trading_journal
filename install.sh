#!/usr/bin/env bash
# CryptoJournal — pre-clone bootstrapper for macOS / Linux.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Grabriel289/trading_journal/main/install.sh | bash
#
# Env overrides:
#   REPO_URL=…    git clone source (default below)
#   INSTALL_DIR=… target directory (default ~/crypto_journal)
#   START=false   skip auto-start; just install
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Grabriel289/trading_journal.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/crypto_journal}"
START="${START:-true}"

bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
ok()    { printf "\033[32m✔\033[0m %s\n" "$*"; }
warn()  { printf "\033[33m!\033[0m %s\n" "$*"; }
die()   { printf "\033[31m✖\033[0m %s\n" "$*" >&2; exit 1; }
step()  { printf "\033[36m→\033[0m %s\n" "$*"; }

# ---------- platform / package-manager detection ----------
OS="$(uname -s)"
case "$OS" in
    Darwin) OS=macos ;;
    Linux)  OS=linux ;;
    *)      die "Unsupported OS: $OS (use install.ps1 for Windows)" ;;
esac

PM=""
if [ "$OS" = macos ]; then
    if command -v brew >/dev/null 2>&1; then PM=brew; fi
elif [ "$OS" = linux ]; then
    for cand in apt-get dnf yum pacman zypper apk; do
        if command -v "$cand" >/dev/null 2>&1; then PM="$cand"; break; fi
    done
fi

pkg_install() {
    # pkg_install <brew-name> <apt-name> <dnf/yum-name> <pacman-name>
    local brew_pkg=$1 apt_pkg=$2 dnf_pkg=$3 pac_pkg=$4
    case "$PM" in
        brew)     brew install "$brew_pkg" ;;
        apt-get)  sudo apt-get update -y >/dev/null && sudo apt-get install -y "$apt_pkg" ;;
        dnf|yum)  sudo "$PM" install -y "$dnf_pkg" ;;
        pacman)   sudo pacman -S --noconfirm "$pac_pkg" ;;
        zypper)   sudo zypper -n install "$dnf_pkg" ;;
        apk)      sudo apk add "$apt_pkg" ;;
        "")       die "No package manager detected. Install $brew_pkg manually and re-run." ;;
    esac
}

ensure_brew_on_macos() {
    [ "$OS" = macos ] || return 0
    # If brew is already on the standard install paths but just not on PATH yet,
    # source its shellenv so the rest of this script can find it.
    if [ -z "$PM" ]; then
        if [ -x /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
            PM=brew
        elif [ -x /usr/local/bin/brew ]; then
            eval "$(/usr/local/bin/brew shellenv)"
            PM=brew
        fi
    fi
    if [ -n "$PM" ]; then
        return 0
    fi
    # Brew is missing. Install it inline so the user only runs ONE command.
    # The trick: when we're inside `curl | bash`, our own stdin is the curl
    # pipe — so Homebrew's installer can't read "Press RETURN" or the sudo
    # password from the user. We redirect its stdin to /dev/tty (the actual
    # keyboard) so password prompts work even inside a piped install.
    if [ ! -r /dev/tty ]; then
        # No terminal available (running over SSH non-interactively, CI, etc.)
        printf '\n\033[31m✖ Homebrew not found and no terminal available for interactive install.\033[0m\n'
        printf 'Install Homebrew first, then re-run:\n\n'
        printf '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"\n'
        printf '  curl -fsSL https://raw.githubusercontent.com/Grabriel289/trading_journal/main/install.sh | bash\n\n'
        exit 1
    fi

    step "Homebrew not found — installing it now"
    printf '\033[33m   You will be asked for your Mac password (the same one you use to log in).\033[0m\n'
    printf '\033[33m   Characters do not appear as you type — that is normal. Press Enter when done.\033[0m\n\n'
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" < /dev/tty

    # After install, brew is on /opt/homebrew (Apple Silicon) or /usr/local (Intel).
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    if command -v brew >/dev/null 2>&1; then
        PM=brew
        ok "Homebrew installed"
    else
        die "Homebrew install failed — please install manually and re-run the CryptoJournal installer"
    fi
}

# ---------- prerequisite checks + auto-install ----------
bold "CryptoJournal install"
echo  "  repo:      $REPO_URL"
echo  "  target:    $INSTALL_DIR"
echo  "  os/pm:     $OS / ${PM:-none}"
echo

ensure_brew_on_macos

if ! command -v git >/dev/null 2>&1; then
    step "Installing git"
    pkg_install git git git git
fi
ok "git $(git --version | awk '{print $3}')"

PYTHON_BIN=""
for cand in python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        v=$("$cand" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")') || continue
        if [ "${v%%.*}" -eq 3 ] && [ "${v##*.}" -ge 10 ]; then
            PYTHON_BIN="$cand"; break
        fi
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    step "Installing Python 3.12"
    pkg_install python@3.12 python3.12 python3 python
    for cand in python3.12 python3.11 python3.10 python3; do
        command -v "$cand" >/dev/null 2>&1 && PYTHON_BIN="$cand" && break
    done
    [ -n "$PYTHON_BIN" ] || die "Python install failed; install Python 3.10+ manually"
fi
ok "$PYTHON_BIN $($PYTHON_BIN --version | awk '{print $2}')"

if ! command -v node >/dev/null 2>&1 \
   || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 18 ]; then
    step "Installing Node.js (LTS)"
    pkg_install node nodejs nodejs nodejs
fi
ok "node $(node --version)"

# ---------- clone (or pull) ----------
if [ -d "$INSTALL_DIR/.git" ]; then
    step "Repository already at $INSTALL_DIR — pulling latest"
    git -C "$INSTALL_DIR" pull --ff-only
else
    if [ -e "$INSTALL_DIR" ]; then
        die "$INSTALL_DIR exists but is not a git repo. Move it or set INSTALL_DIR=…"
    fi
    step "Cloning $REPO_URL → $INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

# ---------- install + (optionally) run ----------
cd "$INSTALL_DIR"
chmod +x dev.sh

if [ "$START" = "true" ]; then
    step "Bootstrapping deps + starting servers"
    exec ./dev.sh
else
    step "Installing deps only (START=false)"
    ./dev.sh --install-only
    echo
    ok "Done. Start the app with:"
    echo "    cd $INSTALL_DIR && ./dev.sh"
fi
