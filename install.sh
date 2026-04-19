#!/usr/bin/env sh
set -eu

BASE_URL="https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main"

echo "Downloading docker-compose.yml..."
curl -fsSL "$BASE_URL/docker-compose.yml" -o docker-compose.yml

if [ -f .env ]; then
  echo ".env already exists, skipping."
else
  echo "Downloading .env..."
  curl -fsSL "$BASE_URL/.env.example" -o .env
fi

echo ""
echo "Done. Next steps:"
echo "  1. Edit .env with your Matrix homeserver details"
echo "  2. Add your bridge token: mkdir -p secrets && echo 'your_token' > secrets/bridge_as_token.txt"
echo "  3. Start the bridge: docker compose up -d"
