#!/bin/sh
# turbo CLI installer — single-file Python 3 script, no dependencies.
#   curl -sSL https://exducer.ai/cli/install.sh | sh
set -e
BASE="https://exducer.ai/cli"
BIN="${TURBO_BIN_DIR:-$HOME/.local/bin}"
command -v python3 >/dev/null 2>&1 || { echo "turbo needs python3 (3.9+)"; exit 1; }
mkdir -p "$BIN"
curl -fsSL "$BASE/turbo.py" -o "$BIN/turbo"
chmod +x "$BIN/turbo"
echo "installed $BIN/turbo"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "add to PATH:  export PATH=\"$BIN:\$PATH\"" ;; esac
echo "next: turbo login   (a write API key from Account -> API keys on cloud.exducer.ai)"
