#!/usr/bin/env bash
# Install gstack Claude Code skills (garrytan/gstack)
# Run once per machine: bash scripts/setup-claude.sh

set -e

if [ ! -d "$HOME/.claude/skills/gstack" ]; then
  echo "Installing gstack to ~/.claude/skills/gstack..."
  git clone https://github.com/garrytan/gstack /tmp/gstack
  cd /tmp/gstack && bun install && bin/dev-setup
  echo "gstack installed."
else
  echo "gstack already installed at ~/.claude/skills/gstack"
fi
