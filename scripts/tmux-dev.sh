#!/usr/bin/env bash

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_NAME="$(basename -s .git "$(git -C "$ROOT" config --get remote.origin.url)")"
BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
# One session per branch/worktree, so parallel worktrees don't collide
# (and matches wt's own $WT_REPO_NAME/$WT_BRANCH session naming).
SESSION="$REPO_NAME/$BRANCH"

attach() {
    if [ -n "$TMUX" ]; then
        tmux switch-client -t "$SESSION"
    else
        tmux attach-session -t "$SESSION"
    fi
}

# Don't create it twice
if tmux has-session -t "$SESSION" 2>/dev/null; then
    attach
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
attach
