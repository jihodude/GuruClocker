#!/bin/bash
# guruclocker for Mac. Double-click this file to run it.
# (First time only: if macOS says it can't be opened, right-click it -> Open -> Open.)

cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"

finish() {
  echo
  read -n 1 -s -r -p "Press any key to close this window."
  echo
  exit "${1:-0}"
}

clear
echo "guruclocker (Mac)"
echo "-----------------"
if [ "$(uname -m)" != "arm64" ]; then
  echo "Note: this Mac has an Intel chip, so speech-to-text will use the slower CPU mode."
fi

# 1. uv: a small free tool that installs Python and this program's parts, without touching the rest of your Mac.
if ! command -v uv >/dev/null 2>&1; then
  echo
  echo "First-time setup: installing 'uv', a small free tool that installs Python for this program."
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
    echo
    echo "Couldn't install uv. Check your internet connection and double-click mac.command again."
    finish 1
  fi
fi

# 2. This program's parts (the first time takes a few minutes; later runs skip this).
if [ ! -d .venv ]; then
  echo
  echo "First-time setup: installing guruclocker's parts. This takes a few minutes..."
fi
QUIET=""; [ -d .venv ] && QUIET="--quiet"
if ! uv sync --frozen --no-dev $QUIET; then
  echo
  echo "Setup failed (see the message above). Check your internet connection and try again."
  finish 1
fi
[ -f .env ] || cp .env.example .env

# 3. Run it.
echo
uv run --frozen --no-dev python -m guruclocker "$@"
finish $?
