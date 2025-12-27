#!/bin/bash

# Script to view bot logs on remote server
# Usage: ./view_logs.sh [user@host] [--follow] [--tail=N]

set -e

# Configuration
REMOTE_HOST="${DEPLOY_HOST:-root@84.35.184.210}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/telegram-bot}"
FOLLOW=false
TAIL=50

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --follow|-f)
            FOLLOW=true
            shift
            ;;
        --tail=*)
            TAIL="${1#*=}"
            shift
            ;;
        *)
            if [[ "$1" =~ @ ]]; then
                REMOTE_HOST="$1"
            fi
            shift
            ;;
    esac
done

# Detect SSH key
SSH_KEY=""
SSH_KEY_PATH="${DEPLOY_SSH_KEY:-$HOME/.ssh/selectel_key}"
if [[ "$SSH_KEY_PATH" == ~* ]]; then
    SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"
fi
if [ -f "$SSH_KEY_PATH" ]; then
    SSH_KEY="-i $SSH_KEY_PATH"
fi

echo "📋 Viewing bot logs from $REMOTE_HOST..."
echo ""

if [ "$FOLLOW" = "true" ]; then
    echo "Following logs (press Ctrl+C to stop)..."
    echo ""
    if [ -n "$SSH_KEY" ]; then
        ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose logs -f --tail=$TAIL bot"
    else
        ssh "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose logs -f --tail=$TAIL bot"
    fi
else
    echo "Last $TAIL lines of logs:"
    echo ""
    if [ -n "$SSH_KEY" ]; then
        ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose logs --tail=$TAIL bot"
    else
        ssh "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose logs --tail=$TAIL bot"
    fi
fi

