#!/usr/bin/env sh
set -eu

BASE_URL="https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main"

echo "Downloading docker-compose.yml..."
curl -fsSL "$BASE_URL/docker-compose.yml" -o docker-compose.yml

echo "Creating config directory..."
mkdir -p config

if [ -f config/bridge.yml ]; then
  echo "config/bridge.yml already exists, skipping."
else
  echo "Downloading config/bridge.yml..."
  curl -fsSL "$BASE_URL/config.yml.example" -o config/bridge.yml
fi

echo ""
echo "Done. Next steps:"
echo "  1. Edit config/bridge.yml with your Matrix homeserver details"
echo "  2. Add your bridge token: mkdir -p secrets && echo 'your_token' > secrets/bridge_as_token.txt"
echo "  3. (Optional) Set server.webhook_secret in config/bridge.yml to require auth"
echo "  4. Start the bridge: docker compose up -d"
