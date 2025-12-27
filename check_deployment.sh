#!/bin/bash

# Script to check if deployment files are on server
# Usage: ./check_deployment.sh [user@host]

set -e

REMOTE_HOST="${1:-root@84.35.184.210}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/telegram-bot}"

# Detect SSH key
SSH_KEY=""
SSH_KEY_PATH="${DEPLOY_SSH_KEY:-$HOME/.ssh/selectel_key}"
if [[ "$SSH_KEY_PATH" == ~* ]]; then
    SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"
fi
if [ -f "$SSH_KEY_PATH" ]; then
    SSH_KEY="-i $SSH_KEY_PATH"
fi

echo "🔍 Checking deployment on $REMOTE_HOST..."
echo ""

if [ -n "$SSH_KEY" ]; then
    ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && echo '=== Files ===' && ls -lah bot/*.py && echo '' && echo '=== handlers.py (first 10 lines) ===' && head -10 bot/handlers.py && echo '' && echo '=== database.py (get_all_employees function) ===' && grep -A 5 'async def get_all_employees' bot/database.py | head -10"
else
    ssh "$REMOTE_HOST" "cd $REMOTE_DIR && echo '=== Files ===' && ls -lah bot/*.py && echo '' && echo '=== handlers.py (first 10 lines) ===' && head -10 bot/handlers.py && echo '' && echo '=== database.py (get_all_employees function) ===' && grep -A 5 'async def get_all_employees' bot/database.py | head -10"
fi

