#!/bin/bash
# ════════════════════════════════════════════════════════════════
# update-xray-sub.sh — Fetch xray subscription, pick best node,
#                      generate config.json, restart container.
# ════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
XRAY_DIR="$PROJECT_DIR/xray"
CONFIG_FILE="$XRAY_DIR/config.json"

# ── Load .env ──
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

SUB_URL="${XRAY_SUBSCRIPTION_URL:-}"

if [ -z "$SUB_URL" ]; then
  echo "❌ XRAY_SUBSCRIPTION_URL not set in .env"
  exit 1
fi

WORKDIR="/tmp/xray-sub-$$"
mkdir -p "$WORKDIR"
trap "rm -rf $WORKDIR" EXIT

# ══════════════════════════════════════════════
# Step 1: Fetch subscription
# ══════════════════════════════════════════════
echo "📡 Fetching subscription..."
curl -sSL --max-time 30 "$SUB_URL" -o "$WORKDIR/sub.b64" 2>/dev/null

if [ ! -s "$WORKDIR/sub.b64" ]; then
  echo "❌ Subscription fetch failed (empty response)"
  exit 1
fi

# ══════════════════════════════════════════════
# Step 2: Decode
# ══════════════════════════════════════════════
# Try base64 decode first; fall back to raw
if base64 -d "$WORKDIR/sub.b64" > "$WORKDIR/sub.txt" 2>/dev/null; then
  echo "✅ Base64 decoded"
else
  echo "ℹ️  Raw content (not base64)"
  cp "$WORKDIR/sub.b64" "$WORKDIR/sub.txt"
fi

# ══════════════════════════════════════════════
# Step 3: Detect format & parse nodes
# ══════════════════════════════════════════════
# We'll write parsed nodes as JSON lines to nodes.jsonl
# Each line: {"type":"vmess|vless|trojan|ss","name":"...","host":"...","port":N,"raw":"...","config":{...}}

# ── 3a: Try JSON array/object first ──
if jq -e 'type == "array" or type == "object"' "$WORKDIR/sub.txt" > /dev/null 2>&1; then
  echo "📦 JSON subscription format detected"
  # If it's a single object with a "out" or "outbounds" key, it's already an xray config
  if jq -e '.outbounds // .out' "$WORKDIR/sub.txt" > /dev/null 2>&1; then
    echo "📋 Direct xray config detected — using as-is"
    jq '.' "$WORKDIR/sub.txt" > "$CONFIG_FILE"
    echo "🔁 Restarting xray container..."
    cd "$PROJECT_DIR" && docker compose restart xray 2>/dev/null || true
    echo "✅ Xray config updated from subscription (direct config)"
    exit 0
  fi
  # Otherwise treat as array of node objects
  # Try to extract outbound configs
  jq -c '.[] // .' "$WORKDIR/sub.txt" > "$WORKDIR/json_lines.txt" 2>/dev/null || true
fi

# ── 3b: Extract URLs from text ──
grep -oP '(vmess|vless|trojan|ss|ssr|hysteria2?|tuic)://[^\s#"]+' "$WORKDIR/sub.txt" > "$WORKDIR/urls.txt" 2>/dev/null || true

URL_COUNT=$(wc -l < "$WORKDIR/urls.txt" 2>/dev/null || echo 0)
echo "📋 Found $URL_COUNT proxy URLs"

if [ "$URL_COUNT" -eq 0 ]; then
  echo "❌ No proxy nodes found in subscription"
  exit 1
fi

# ══════════════════════════════════════════════
# Step 4: Parse each URL into xray outbound JSON
# ══════════════════════════════════════════════
> "$WORKDIR/parsed_nodes.jsonl"

while IFS= read -r url; do
  [ -z "$url" ] && continue
  PROTO=$(echo "$url" | cut -d: -f1)

  case "$PROTO" in
    vmess)
      # vmess://base64(json) — decode the base64 part
      B64=$(echo "$url" | sed 's|^vmess://||')
      JSON=$(echo "$B64" | base64 -d 2>/dev/null || echo "")
      if [ -z "$JSON" ] || ! echo "$JSON" | jq -e '.' > /dev/null 2>&1; then
        echo "  ⚠️  Failed to decode vmess: ${url:0:60}..."
        continue
      fi

      HOST=$(echo "$JSON" | jq -r '.add // .host // empty')
      PORT=$(echo "$JSON" | jq -r '.port // empty')
      UUID=$(echo "$JSON" | jq -r '.id // empty')
      NAME=$(echo "$JSON" | jq -r '.ps // empty')
      NET=$(echo "$JSON" | jq -r '.net // "tcp"')
      TLS=$(echo "$JSON" | jq -r '.tls // ""')
      PATH=$(echo "$JSON" | jq -r '.path // ""')
      VHOST=$(echo "$JSON" | jq -r '.host // ""')
      SCYPE=$(echo "$JSON" | jq -r '.type // "auto"')
      AID=$(echo "$JSON" | jq -r '.aid // "0"')
      SNI=$(echo "$JSON" | jq -r '.sni // ""')
      FP=$(echo "$JSON" | jq -r '.fp // ""')
      ALPN=$(echo "$JSON" | jq -r '.alpn // ""')

      [ -z "$HOST" ] || [ -z "$PORT" ] || [ -z "$UUID" ] && continue

      # Build streamSettings
      STREAM_NET="$NET"
      STREAM_TCP="{}"
      STREAM_WS="{}"
      STREAM_TLS="{}"

      if [ "$NET" = "ws" ]; then
        STREAM_WS=$(jq -n --arg path "$PATH" --arg host "$VHOST" '{path: $path, headers: {Host: $host}}')
      elif [ "$NET" = "grpc" ]; then
        STREAM_WS=$(jq -n --arg sn "$(echo "$JSON" | jq -r '.path // ""')" '{serviceName: $sn}')
      fi

      if [ "$TLS" = "tls" ]; then
        STREAM_TLS=$(jq -n \
          --arg serverName "${SNI:-$HOST}" \
          --arg fp "${FP:-}" \
          --arg alpn "${ALPN:-}" \
          '{serverName: $serverName, allowInsecure: false, fingerprint: (if $fp != "" then $fp else "chrome" end), alpn: (if $alpn != "" then ($alpn | split(",")) else null end)}')
      fi

      OUTBOUND=$(jq -n \
        --arg host "$HOST" \
        --arg port "$PORT" \
        --arg uuid "$UUID" \
        --arg aid "$AID" \
        --arg net "$STREAM_NET" \
        --arg scype "$SCYPE" \
        --arg name "${NAME:-$HOST}" \
        --argjson tcp "$STREAM_TCP" \
        --argjson ws "$STREAM_WS" \
        --argjson tls "$STREAM_TLS" \
        '{
          protocol: "vmess",
          settings: {
            vnext: [{
              address: $host,
              port: ($port | tonumber),
              users: [{
                id: $uuid,
                alterId: ($aid | tonumber),
                security: "auto"
              }]
            }]
          },
          streamSettings: {
            network: $net,
            security: (if $tls != {} then "tls" else "none" end),
            tcpSettings: $tcp,
            wsSettings: $ws,
            tlsSettings: $tls
          },
          tag: "proxy"
        }')

      echo "$OUTBOUND" | jq -c --arg name "${NAME:-$HOST}" --arg host "$HOST" --arg port "$PORT" \
        '{type:"vmess", name:$name, host:$host, port:($port|tonumber), config:., raw:""}' \
        >> "$WORKDIR/parsed_nodes.jsonl"
      ;;

    vless)
      # vless://uuid@host:port?params#name
      BODY=$(echo "$url" | sed 's|^vless://||')
      NAME=$(echo "$BODY" | sed -n 's|.*#||p')
      BODY_NO_NAME=$(echo "$BODY" | sed 's|#.*||')

      UUID=$(echo "$BODY_NO_NAME" | cut -d@ -f1)
      REST=$(echo "$BODY_NO_NAME" | cut -d@ -f2)
      HOST=$(echo "$REST" | cut -d: -f1)
      PORT_PARAMS=$(echo "$REST" | cut -d: -f2)
      PORT=$(echo "$PORT_PARAMS" | cut -d? -f1)
      PARAMS=$(echo "$PORT_PARAMS" | cut -d? -f2)

      [ -z "$HOST" ] || [ -z "$PORT" ] || [ -z "$UUID" ] && continue

      # Parse query params
      NET=$(echo "$PARAMS" | grep -oP 'net=\K[^&]+' || echo "tcp")
      TLS=$(echo "$PARAMS" | grep -oP 'security=\K[^&]+' || echo "none")
      SNI=$(echo "$PARAMS" | grep -oP 'sni=\K[^&]+' || echo "")
      FP=$(echo "$PARAMS" | grep -oP 'fp=\K[^&]+' || echo "")
      PATH=$(echo "$PARAMS" | grep -oP 'path=\K[^&]+' || echo "")
      HOST_PARAM=$(echo "$PARAMS" | grep -oP 'host=\K[^&]+' || echo "")
      TYPE=$(echo "$PARAMS" | grep -oP 'type=\K[^&]+' || echo "tcp")

      # Build streamSettings
      STREAM_WS="{}"
      STREAM_TLS="{}"

      if [ "$NET" = "ws" ]; then
        STREAM_WS=$(jq -n --arg path "$PATH" --arg host "${HOST_PARAM:-$HOST}" '{path: $path, headers: {Host: $host}}')
      elif [ "$NET" = "grpc" ]; then
        STREAM_WS=$(jq -n --arg sn "$(echo "$PARAMS" | grep -oP 'serviceName=\K[^&]+' || echo "")" '{serviceName: $sn}')
      fi

      if [ "$TLS" = "tls" ]; then
        STREAM_TLS=$(jq -n \
          --arg serverName "${SNI:-$HOST}" \
          --arg fp "${FP:-}" \
          '{serverName: $serverName, allowInsecure: false, fingerprint: (if $fp != "" then $fp else "chrome" end)}')
      fi

      OUTBOUND=$(jq -n \
        --arg host "$HOST" \
        --arg port "$PORT" \
        --arg uuid "$UUID" \
        --arg net "$NET" \
        --arg name "${NAME:-$HOST}" \
        --argjson ws "$STREAM_WS" \
        --argjson tls "$STREAM_TLS" \
        '{
          protocol: "vless",
          settings: {
            vnext: [{
              address: $host,
              port: ($port | tonumber),
              users: [{
                id: $uuid,
                encryption: "none"
              }]
            }]
          },
          streamSettings: {
            network: $net,
            security: (if $tls != {} then "tls" else "none" end),
            wsSettings: $ws,
            tlsSettings: $tls
          },
          tag: "proxy"
        }')

      echo "$OUTBOUND" | jq -c --arg name "${NAME:-$HOST}" --arg host "$HOST" --arg port "$PORT" \
        '{type:"vless", name:$name, host:$host, port:($port|tonumber), config:., raw:""}' \
        >> "$WORKDIR/parsed_nodes.jsonl"
      ;;

    trojan)
      # trojan://password@host:port?params#name
      BODY=$(echo "$url" | sed 's|^trojan://||')
      NAME=$(echo "$BODY" | sed -n 's|.*#||p')
      BODY_NO_NAME=$(echo "$BODY" | sed 's|#.*||')

      PASS=$(echo "$BODY_NO_NAME" | cut -d@ -f1)
      REST=$(echo "$BODY_NO_NAME" | cut -d@ -f2)
      HOST=$(echo "$REST" | cut -d: -f1)
      PORT_PARAMS=$(echo "$REST" | cut -d: -f2)
      PORT=$(echo "$PORT_PARAMS" | cut -d? -f1)
      PARAMS=$(echo "$PORT_PARAMS" | cut -d? -f2)

      [ -z "$HOST" ] || [ -z "$PORT" ] || [ -z "$PASS" ] && continue

      SNI=$(echo "$PARAMS" | grep -oP 'sni=\K[^&]+' || echo "")
      FP=$(echo "$PARAMS" | grep -oP 'fp=\K[^&]+' || echo "")
      NET=$(echo "$PARAMS" | grep -oP 'type=\K[^&]+' || echo "tcp")
      PATH=$(echo "$PARAMS" | grep -oP 'path=\K[^&]+' || echo "")

      STREAM_TLS=$(jq -n \
        --arg serverName "${SNI:-$HOST}" \
        --arg fp "${FP:-}" \
        '{serverName: $serverName, allowInsecure: false, fingerprint: (if $fp != "" then $fp else "chrome" end)}')

      STREAM_WS="{}"
      if [ "$NET" = "ws" ]; then
        STREAM_WS=$(jq -n --arg path "$PATH" '{path: $path, headers: {}}')
      fi

      OUTBOUND=$(jq -n \
        --arg host "$HOST" \
        --arg port "$PORT" \
        --arg pass "$PASS" \
        --arg net "$NET" \
        --argjson tls "$STREAM_TLS" \
        --argjson ws "$STREAM_WS" \
        '{
          protocol: "trojan",
          settings: {
            servers: [{
              address: $host,
              port: ($port | tonumber),
              password: $pass
            }]
          },
          streamSettings: {
            network: $net,
            security: "tls",
            tlsSettings: $tls,
            wsSettings: $ws
          },
          tag: "proxy"
        }')

      echo "$OUTBOUND" | jq -c --arg name "${NAME:-$HOST}" --arg host "$HOST" --arg port "$PORT" \
        '{type:"trojan", name:$name, host:$host, port:($port|tonumber), config:., raw:""}' \
        >> "$WORKDIR/parsed_nodes.jsonl"
      ;;

    ss)
      # ss://base64(method:password)@host:port#name
      # or ss://base64(method:password@host:port)#name
      BODY=$(echo "$url" | sed 's|^ss://||')
      NAME=$(echo "$BODY" | sed -n 's|.*#||p')
      BODY_NO_NAME=$(echo "$BODY" | sed 's|#.*||')

      if echo "$BODY_NO_NAME" | grep -q '@'; then
        B64_PART=$(echo "$BODY_NO_NAME" | cut -d@ -f1)
        REST=$(echo "$BODY_NO_NAME" | cut -d@ -f2)
        HOST=$(echo "$REST" | cut -d: -f1)
        PORT=$(echo "$REST" | cut -d: -f2 | cut -d? -f1)
        DECODED=$(echo "$B64_PART" | base64 -d 2>/dev/null || echo "")
        METHOD=$(echo "$DECODED" | cut -d: -f1)
        PASSWORD=$(echo "$DECODED" | cut -d: -f2-)
      else
        DECODED=$(echo "$BODY_NO_NAME" | base64 -d 2>/dev/null || echo "")
        HOST=$(echo "$DECODED" | grep -oP '@\K[^:]+' || echo "")
        PORT=$(echo "$DECODED" | grep -oP ':\K[0-9]+' || echo "")
        METHOD=$(echo "$DECODED" | cut -d: -f1)
        PASSWORD=$(echo "$DECODED" | sed 's|^.*:[^:]*@||' | sed 's|:.*||')
      fi

      [ -z "$HOST" ] || [ -z "$PORT" ] && continue

      OUTBOUND=$(jq -n \
        --arg host "$HOST" \
        --arg port "$PORT" \
        --arg method "${METHOD:-aes-256-gcm}" \
        --arg password "${PASSWORD:-}" \
        '{
          protocol: "shadowsocks",
          settings: {
            servers: [{
              address: $host,
              port: ($port | tonumber),
              method: $method,
              password: $password
            }]
          },
          tag: "proxy"
        }')

      echo "$OUTBOUND" | jq -c --arg name "${NAME:-$HOST}" --arg host "$HOST" --arg port "$PORT" \
        '{type:"ss", name:$name, host:$host, port:($port|tonumber), config:., raw:""}' \
        >> "$WORKDIR/parsed_nodes.jsonl"
      ;;

    *)
      echo "  ⚠️  Unsupported protocol: $PROTO"
      ;;
  esac
done < "$WORKDIR/urls.txt"

NODE_COUNT=$(wc -l < "$WORKDIR/parsed_nodes.jsonl" 2>/dev/null || echo 0)
echo "📋 Parsed $NODE_COUNT nodes"

if [ "$NODE_COUNT" -eq 0 ]; then
  echo "❌ No parseable nodes found"
  exit 1
fi

# ══════════════════════════════════════════════
# Step 5: Ping each node and find fastest
# ══════════════════════════════════════════════
echo "🏓 Pinging nodes..."

BEST_PING=99999
BEST_LINE=""
INDEX=0

while IFS= read -r line; do
  NAME=$(echo "$line" | jq -r '.name')
  HOST=$(echo "$line" | jq -r '.host')
  IDX=$((INDEX + 1))

  # Ping (1 packet, 2s timeout)
  PING_RAW=$(ping -c 1 -W 2 "$HOST" 2>/dev/null | grep -oP 'time=\K[0-9.]+' | head -1 || echo "")

  if [ -z "$PING_RAW" ]; then
    echo "  $IDX. $NAME ($HOST) → ❌ unreachable"
    INDEX=$((INDEX + 1))
    continue
  fi

  echo "  $IDX. $NAME ($HOST) → ${PING_RAW}ms"

  # Compare (integer comparison for simplicity)
  PING_INT=$(echo "$PING_RAW" | cut -d. -f1)
  [ -z "$PING_INT" ] && PING_INT=99999

  if [ "$PING_INT" -lt "$BEST_PING" ]; then
    BEST_PING=$PING_INT
    BEST_LINE="$line"
  fi

  INDEX=$((INDEX + 1))
done < "$WORKDIR/parsed_nodes.jsonl"

if [ -z "$BEST_LINE" ]; then
  echo "❌ No reachable nodes found"
  exit 1
fi

BEST_NAME=$(echo "$BEST_LINE" | jq -r '.name')
BEST_HOST=$(echo "$BEST_LINE" | jq -r '.host')
echo ""
echo "🏆 Best node: $BEST_NAME ($BEST_HOST) → ${BEST_PING}ms"

# ══════════════════════════════════════════════
# Step 6: Generate xray config.json
# ══════════════════════════════════════════════
BEST_OUTBOUND=$(echo "$BEST_LINE" | jq '.config')

# Merge with base inbound config
jq -n \
  --argjson outbound "$BEST_OUTBOUND" \
  '{
    log: { loglevel: "warning" },
    inbounds: [
      {
        port: 1080,
        protocol: "socks",
        settings: { auth: "noauth", udp: true }
      },
      {
        port: 1081,
        protocol: "http",
        settings: {}
      }
    ],
    outbounds: [
      $outbound,
      {
        protocol: "freedom",
        tag: "direct"
      },
      {
        protocol: "blackhole",
        tag: "block"
      }
    ],
    routing: {
      domainStrategy: "AsIs",
      rules: [
        {
          type: "field",
          domain: ["geosite:category-ads-all"],
          outboundTag: "block"
        },
        {
          type: "field",
          outboundTag: "proxy",
          network: "tcp,udp"
        }
      ]
    }
  }' > "$CONFIG_FILE"

echo "📝 Config written to $CONFIG_FILE"

# ══════════════════════════════════════════════
# Step 7: Restart xray container
# ══════════════════════════════════════════════
echo "🔁 Restarting xray container..."
cd "$PROJECT_DIR"

if docker compose ps xray 2>/dev/null | grep -q "running"; then
  docker compose restart xray
  sleep 3
  if docker compose ps xray 2>/dev/null | grep -q "running"; then
    echo "✅ Xray restarted → using $BEST_NAME (${BEST_PING}ms)"
  else
    echo "⚠️  Xray container failed to start. Check logs: docker compose logs xray"
  fi
else
  echo "ℹ️  Xray container not running. Start with: docker compose up -d xray"
fi
