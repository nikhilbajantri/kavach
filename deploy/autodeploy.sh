#!/usr/bin/env bash
# Pull-based continuous deployment for the KAVACH backend.
# Runs every minute from kavach-deploy.timer: if origin/main moved, rebuild and restart.
# Pull-based on purpose: no SSH keys or cloud credentials ever live in GitHub.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/ubuntu/kavach}"
BRANCH="${BRANCH:-main}"
COMPOSE=(docker compose -f "$REPO_DIR/deploy/docker-compose.ec2.yml")

exec 9>/tmp/kavach-deploy.lock
flock -n 9 || exit 0  # a deploy is already running

cd "$REPO_DIR"
git fetch --quiet origin "$BRANCH"
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [[ "$LOCAL" == "$REMOTE" && "${1:-}" != "--force" ]]; then
  exit 0
fi

echo "$(date -Is) deploying $REMOTE (was $LOCAL)"
git reset --hard --quiet "origin/$BRANCH"
"${COMPOSE[@]}" up -d --build --remove-orphans
docker image prune -f >/dev/null
echo "$(date -Is) deployed $(git log -1 --format='%h %s')"
