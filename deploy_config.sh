#!/bin/bash

# Deployment configuration
# You can override these values by setting environment variables

# Remote server connection
export DEPLOY_HOST="${DEPLOY_HOST:-root@84.35.184.210}"
export DEPLOY_DIR="${DEPLOY_DIR:-/opt/telegram-bot}"

# SSH key path (optional)
export DEPLOY_SSH_KEY="${DEPLOY_SSH_KEY:-~/.ssh/selectel_key}"

# Deployment options
export DEPLOY_REBUILD="${DEPLOY_REBUILD:-false}"  # Set to "true" to rebuild Docker images
export DEPLOY_SHOW_LOGS="${DEPLOY_SHOW_LOGS:-true}"  # Show logs after deployment

