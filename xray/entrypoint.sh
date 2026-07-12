#!/bin/sh
set -e

CONFIG="/etc/xray/config.json"

if [ ! -f "$CONFIG" ]; then
  echo "No xray config found, creating default (direct outbound)..."
  cat > "$CONFIG" << 'EOF'
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "port": 1080,
      "protocol": "socks",
      "settings": { "auth": "noauth", "udp": true }
    },
    {
      "port": 1081,
      "protocol": "http",
      "settings": {}
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct"
    }
  ]
}
EOF
fi

echo "Starting xray..."
exec /usr/local/bin/xray run -config "$CONFIG"
