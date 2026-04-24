#!/usr/bin/env sh
set -eu

BASE_URL="https://raw.githubusercontent.com/krahlos/matrix-webhook-bridge/main"

for path in docker-compose.yml config tokens bridge-registration.yml; do
  if [ -e "$path" ]; then
    echo "Error: '$path' already exists. Run this installer in an empty directory." >&2
    exit 1
  fi
done

echo "Downloading docker-compose.yml..."
curl -fsSL "$BASE_URL/docker-compose.yml" -o docker-compose.yml

echo "Downloading config/bridge.yml..."
mkdir config
curl -fsSL "$BASE_URL/bridge.yml.example" -o config/bridge.yml

echo "Generating tokens and bootstrapping bridge-registration.yml..."
mkdir tokens
AS_TOKEN=$(openssl rand -hex 32)
HS_TOKEN=$(openssl rand -hex 32)
echo "$AS_TOKEN" > tokens/bridge_as_token.txt
curl -fsSL "$BASE_URL/bridge-registration.yml.example" -o bridge-registration.yml
sed -i "s/<your_as_token_here>/$AS_TOKEN/g" bridge-registration.yml
sed -i "s/<your_hs_token_here>/$HS_TOKEN/g" bridge-registration.yml

echo ""
echo "Done. Next steps:"
echo "  1. Edit config/bridge.yml with your Matrix homeserver details"
echo "  2. Register the Application Service with your homeserver (see INSTALL.md for details)"
echo "  3. (Optional) Set server.webhook_secret in config/bridge.yml to require auth"
echo "  4. Start the bridge: docker compose up -d"
