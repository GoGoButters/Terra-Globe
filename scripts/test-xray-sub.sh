#!/bin/bash
# ──────────────────────────────────────────────────────
# test-xray-sub.sh — Debug: download & inspect subscription
# ──────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

SUB_URL="${XRAY_SUBSCRIPTION_URL:-}"

if [ -z "$SUB_URL" ]; then
  echo "❌ XRAY_SUBSCRIPTION_URL not set in .env"
  echo "   Add it to $PROJECT_DIR/.env"
  exit 1
fi

WORKDIR="/tmp/xray-sub-debug-$$"
mkdir -p "$WORKDIR"
trap "rm -rf $WORKDIR" EXIT

echo "═══════════════════════════════════════════════"
echo "📡 Xray Subscription Debugger"
echo "═══════════════════════════════════════════════"
echo ""
echo "URL: ${SUB_URL:0:40}..."
echo ""

# Fetch
echo "── Step 1: Fetching subscription ──"
HTTP_CODE=$(curl -sSL --max-time 30 -w "%{http_code}" -o "$WORKDIR/sub.b64" "$SUB_URL" 2>/dev/null || true)
echo "HTTP status: $HTTP_CODE"
echo "Raw size: $(wc -c < "$WORKDIR/sub.b64") bytes"

if [ ! -s "$WORKDIR/sub.b64" ]; then
  echo "❌ Empty response"
  exit 1
fi

# Show raw content (first 200 chars)
echo ""
echo "── Raw content (first 200 chars) ──"
head -c 200 "$WORKDIR/sub.b64"
echo ""
echo ""

# Try base64 decode
echo "── Step 2: Base64 decode ──"
if base64 -d "$WORKDIR/sub.b64" > "$WORKDIR/sub.txt" 2>/dev/null; then
  echo "✅ Base64 decode successful"
  echo "Decoded size: $(wc -c < "$WORKDIR/sub.txt") bytes"
else
  echo "⚠️  Not valid base64, using raw content"
  cp "$WORKDIR/sub.b64" "$WORKDIR/sub.txt"
fi

echo ""
echo "── Decoded content (first 500 chars) ──"
head -c 500 "$WORKDIR/sub.txt"
echo ""
echo ""

# Try JSON parse
echo "── Step 3: Checking JSON format ──"
if jq -e '.' "$WORKDIR/sub.txt" > /dev/null 2>&1; then
  echo "✅ Valid JSON"
  echo "JSON type: $(jq -r 'if type == "array" then "array[\(. | length)]" elif type == "object" then "object{\(. | keys | join(","))}" else type end' "$WORKDIR/sub.txt")"
  echo ""
  echo "── JSON preview ──"
  jq '.' "$WORKDIR/sub.txt" | head -c 2000
  echo ""
elif jq -e '.' "$WORKDIR/sub.b64" > /dev/null 2>&1; then
  echo "✅ Raw content is valid JSON"
  jq '.' "$WORKDIR/sub.b64" | head -c 2000
  echo ""
else
  echo "Not JSON"
fi

echo ""

# Extract URLs
echo "── Step 4: Extracting proxy URLs ──"
grep -oP '(vmess|vless|trojan|ss|ssr|hysteria|hysteria2|tuic|socks|http)://[^\s#"]+' "$WORKDIR/sub.txt" > "$WORKDIR/urls.txt" 2>/dev/null || true
URL_COUNT=$(wc -l < "$WORKDIR/urls.txt" 2>/dev/null || echo 0)
echo "Found $URL_COUNT proxy URLs"

if [ "$URL_COUNT" -gt 0 ]; then
  echo ""
  echo "── URLs found ──"
  i=1
  while IFS= read -r url; do
    PROTO=$(echo "$url" | cut -d: -f1)
    NAME=$(echo "$url" | sed -n 's|.*#||p')
    HOST=$(echo "$url" | sed -n 's|.*@\([^:]*\).*|\1|p')
    echo "  $i. [$PROTO] ${NAME:-$HOST} → ${url:0:80}..."
    i=$((i + 1))
  done < "$WORKDIR/urls.txt"
fi

echo ""

# Also check for base64-encoded sub-subscriptions
echo "── Step 5: Checking for nested base64 ──"
grep -oP '[A-Za-z0-9+/]{40,}={0,2}' "$WORKDIR/sub.txt" > "$WORKDIR/b64_candidates.txt" 2>/dev/null || true
NESTED_COUNT=$(wc -l < "$WORKDIR/b64_candidates.txt" 2>/dev/null || echo 0)
echo "Found $NESTED_COUNT base64-like strings"

# Check for SIP002 / Shadowsocks format
echo ""
echo "── Step 6: Checking Shadowsocks (SIP002) format ──"
grep -oP 'ss://[^\s#"]+' "$WORKDIR/sub.txt" > "$WORKDIR/ss_urls.txt" 2>/dev/null || true
SS_COUNT=$(wc -l < "$WORKDIR/ss_urls.txt" 2>/dev/null || echo 0)
echo "Found $SS_COUNT ss:// URLs"

if [ "$SS_COUNT" -gt 0 ]; then
  while IFS= read -r url; do
    # Try to decode ss:// base64 part
    B64_PART=$(echo "$url" | sed 's|ss://||' | cut -d@ -f1)
    DECODED=$(echo "$B64_PART" | base64 -d 2>/dev/null || echo "decode failed")
    echo "  $url"
    echo "    → decoded: $DECODED"
  done < "$WORKDIR/ss_urls.txt"
fi

# Check for vmess base64 format
echo ""
echo "── Step 7: Checking VMess format ──"
grep -oP 'vmess://[^\s#"]+' "$WORKDIR/sub.txt" > "$WORKDIR/vmess_urls.txt" 2>/dev/null || true
VMESS_COUNT=$(wc -l < "$WORKDIR/vmess_urls.txt" 2>/dev/null || echo 0)
echo "Found $VMESS_COUNT vmess:// URLs"

if [ "$VMESS_COUNT" -gt 0 ]; then
  while IFS= read -r url; do
    B64_PART=$(echo "$url" | sed 's|vmess://||')
    DECODED=$(echo "$B64_PART" | base64 -d 2>/dev/null || echo "decode failed")
    echo "  vmess → $DECODED" | head -c 200
    echo ""
  done < "$WORKDIR/vmess_urls.txt"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "✅ Debug complete. Check output above."
echo "═══════════════════════════════════════════════"
