#!/usr/bin/env bash

set -e

SESSION="dev"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Don't create it twice
if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux attach-session -t "$SESSION"
    exit 0
fi

# Backend
tmux new-session -d -s "$SESSION" -n backend -c "$ROOT/backend"
tmux send-keys -t "$SESSION:backend" "make dev" C-m

# Frontend
tmux new-window -t "$SESSION" -n frontend -c "$ROOT/frontend"
tmux send-keys -t "$SESSION:frontend" "make dev" C-m

# Claude
tmux new-window -t "$SESSION" -n claude -c "$ROOT"
tmux send-keys -t "$SESSION:claude" "claude" C-m

# Shell
tmux new-window -t "$SESSION" -n shell -c "$ROOT"

# Start on shell
tmux select-window -t "$SESSION:shell"

# Attach
tmux attach-session -t "$SESSION"
