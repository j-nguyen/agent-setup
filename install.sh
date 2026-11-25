#!/usr/bin/env sh
# One-command setup for agent-setup. Safe to re-run.
#
#   ./install.sh            check prerequisites, preview, install, verify
#   ./install.sh --yes      same, without the confirmation prompt (for agents / CI)
#   ./install.sh --no-path  don't add `agent-setup` to ~/.local/bin
#   ./install.sh --trackers=github,jira   choose ticket trackers without the prompt
#                                         (github, jira, gitlab, linear, or none)
#   ./install.sh --only=review-changes,memory   install only these items (and what they need)
#   ./install.sh --skip=record-feature          install everything except these items
set -eu

REPO=$(cd "$(dirname "$0")" && pwd)
BIN="$REPO/bin/agent-setup"
YES=0
LINK=1
TRACKERS=""
ONLY=""
SKIP=""
for arg in "$@"; do
  case "$arg" in
    -y|--yes) YES=1 ;;
    --no-path) LINK=0 ;;
    --trackers=*) TRACKERS="${arg#--trackers=}" ;;
    --trackers) echo "use --trackers=github,jira (with =)" >&2; exit 2 ;;
    --only=*) ONLY="${arg#--only=}" ;;
    --only) echo "use --only=review-changes,memory (with =)" >&2; exit 2 ;;
    --skip=*) SKIP="${arg#--skip=}" ;;
    --skip) echo "use --skip=record-feature (with =)" >&2; exit 2 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
if [ -n "$ONLY" ] && [ -n "$SKIP" ]; then
  echo "use --only or --skip, not both" >&2; exit 2
fi

say() { printf '\n== %s\n' "$1"; }

say "Checking prerequisites"
command -v python3 >/dev/null 2>&1 || { echo "python3 not found: install Python 3.11+" >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "Python 3.11+ required (found $(python3 -V 2>&1))" >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "git not found" >&2; exit 1; }
for t in claude codex opencode; do
  if command -v "$t" >/dev/null 2>&1; then echo "  found $t"; else echo "  $t not installed (its files are still written, ready for later)"; fi
done
chmod +x "$BIN"

say "Validating sources"
"$BIN" validate

say "Ticket trackers"
if [ -n "$TRACKERS" ]; then
  "$BIN" trackers --set "$TRACKERS"
elif [ "$YES" -ne 1 ] && [ -t 0 ]; then
  "$BIN" trackers --ask
else
  echo "  skipped (non-interactive). Pasted tickets work; choose later with: agent-setup trackers --ask"
fi

say "Choose what to install"
if [ -n "$ONLY" ]; then
  "$BIN" select --only "$ONLY"
elif [ -n "$SKIP" ]; then
  "$BIN" select --skip "$SKIP"
elif [ "$YES" -ne 1 ] && [ -t 0 ]; then
  "$BIN" select --ask
else
  echo "  keeping your saved choice, or everything if there is none. Change it later with: agent-setup select --ask"
fi

say "Preview (nothing is changed yet)"
set +e
"$BIN" sync --dry-run
preview=$?
set -e
if [ "$preview" -ne 0 ]; then
  cat >&2 <<'EOF'

Some targets already exist and aren't managed by agent-setup (CONFLICT lines above).
Nothing was changed. Rename or remove those, or for MCP servers re-run sync with
--adopt to take them over, then run ./install.sh again. See INSTALL.md, "Conflicts".
EOF
  exit 1
fi

if [ "$YES" -ne 1 ]; then
  printf '\nInstall the above? [y/N] '
  read -r answer
  case "$answer" in y|Y|yes|YES) ;; *) echo "Cancelled; nothing changed."; exit 0 ;; esac
fi

say "Installing"
if [ "$YES" -eq 1 ]; then
  "$BIN" sync --yes
else
  "$BIN" sync
fi

if [ "$LINK" -eq 1 ]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$BIN" "$HOME/.local/bin/agent-setup"
  echo "  linked ~/.local/bin/agent-setup -> $BIN"
  case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "  note: add ~/.local/bin to your PATH to run 'agent-setup' directly" ;; esac
fi

say "Verifying"
"$BIN" doctor || true

cat <<'EOF'

Done. Remaining steps:
  - If doctor listed MCP sign-ins as "todo", do those (they open a browser):
      Claude Code: /mcp   Codex: codex mcp login <name>   OpenCode: opencode mcp auth <name>
  - Restart any open Claude Code / Codex / OpenCode sessions to pick up the new skills.

Try it: in any repo, ask "review my changes" or "does issue #123 reproduce?".
EOF
