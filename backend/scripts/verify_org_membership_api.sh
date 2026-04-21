#!/usr/bin/env bash
set -euo pipefail

# Org Membership API verification script
# Requires: curl, jq
#
# Usage:
#   API_BASE="http://localhost:8000/api/v1" \
#   OWNER_TOKEN="..." \
#   ADMIN_TOKEN="..." \
#   MEMBER_TOKEN="..." \
#   OUTSIDER_TOKEN="..." \
#   ORG_ID="1" \
#   TARGET_USER_ID="123" \
#   ./backend/scripts/verify_org_membership_api.sh
#
# Optional:
#   INVITE_EMAIL="new.user@example.com"
#   PROMOTE_ROLE="admin"   # admin|member

API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
OWNER_TOKEN="${OWNER_TOKEN:-}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
MEMBER_TOKEN="${MEMBER_TOKEN:-}"
OUTSIDER_TOKEN="${OUTSIDER_TOKEN:-}"
ORG_ID="${ORG_ID:-}"
TARGET_USER_ID="${TARGET_USER_ID:-}"
INVITE_EMAIL="${INVITE_EMAIL:-invitee.$(date +%s)@example.com}"
PROMOTE_ROLE="${PROMOTE_ROLE:-admin}"

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required."
  exit 1
fi

if [[ -z "$OWNER_TOKEN" || -z "$ADMIN_TOKEN" || -z "$MEMBER_TOKEN" || -z "$OUTSIDER_TOKEN" || -z "$ORG_ID" || -z "$TARGET_USER_ID" ]]; then
  echo "ERROR: Missing required env vars."
  echo "Required: OWNER_TOKEN, ADMIN_TOKEN, MEMBER_TOKEN, OUTSIDER_TOKEN, ORG_ID, TARGET_USER_ID"
  exit 1
fi

pass_count=0
fail_count=0

report() {
  local ok="$1"
  local label="$2"
  local details="${3:-}"
  if [[ "$ok" == "1" ]]; then
    pass_count=$((pass_count + 1))
    echo "[PASS] $label"
  else
    fail_count=$((fail_count + 1))
    echo "[FAIL] $label"
    [[ -n "$details" ]] && echo "       $details"
  fi
}

request() {
  local method="$1"
  local path="$2"
  local token="$3"
  local body="${4:-}"

  if [[ -n "$body" ]]; then
    curl -sS -X "$method" \
      "$API_BASE$path" \
      -H "Authorization: Bearer $token" \
      -H "Content-Type: application/json" \
      -d "$body" \
      -w "\nHTTP_STATUS:%{http_code}"
  else
    curl -sS -X "$method" \
      "$API_BASE$path" \
      -H "Authorization: Bearer $token" \
      -w "\nHTTP_STATUS:%{http_code}"
  fi
}

split_status() {
  local raw="$1"
  local status
  status="$(echo "$raw" | sed -n 's/^HTTP_STATUS://p')"
  local body
  body="$(echo "$raw" | sed '/^HTTP_STATUS:/d')"
  echo "$status"
  echo "$body"
}

echo "== Org Membership API Verification =="
echo "API: $API_BASE"
echo "ORG_ID: $ORG_ID"
echo

# 1) Member list read access
raw="$(request GET "/orgs/$ORG_ID/members" "$MEMBER_TOKEN")"
status="$(split_status "$raw" | sed -n '1p')"
body="$(split_status "$raw" | sed -n '2,$p')"
if [[ "$status" == "200" ]]; then
  report 1 "MEMBER can list members"
else
  report 0 "MEMBER can list members" "Expected 200, got $status, body: $body"
fi

# 2) Same-org isolation
raw="$(request GET "/orgs/$ORG_ID/members" "$OUTSIDER_TOKEN")"
status="$(split_status "$raw" | sed -n '1p')"
body="$(split_status "$raw" | sed -n '2,$p')"
if [[ "$status" == "403" ]]; then
  report 1 "OUTSIDER cannot list foreign org members"
else
  report 0 "OUTSIDER cannot list foreign org members" "Expected 403, got $status, body: $body"
fi

# 3) Role gate: MEMBER invite forbidden
raw="$(request POST "/orgs/$ORG_ID/invites" "$MEMBER_TOKEN" "{\"email\":\"$INVITE_EMAIL\",\"role\":\"member\"}")"
status="$(split_status "$raw" | sed -n '1p')"
body="$(split_status "$raw" | sed -n '2,$p')"
if [[ "$status" == "403" ]]; then
  report 1 "MEMBER cannot create invites"
else
  report 0 "MEMBER cannot create invites" "Expected 403, got $status, body: $body"
fi

# 4) ADMIN/OWNER invite allowed
raw="$(request POST "/orgs/$ORG_ID/invites" "$ADMIN_TOKEN" "{\"email\":\"$INVITE_EMAIL\",\"role\":\"member\"}")"
status="$(split_status "$raw" | sed -n '1p')"
body="$(split_status "$raw" | sed -n '2,$p')"
invite_token=""
if [[ "$status" == "201" ]]; then
  invite_token="$(echo "$body" | jq -r '.token // empty')"
  report 1 "ADMIN/OWNER can create invites"
else
  report 0 "ADMIN/OWNER can create invites" "Expected 201, got $status, body: $body"
fi

# 5) Accept invite (requires token + your auth user to match invite email)
if [[ -n "$invite_token" ]]; then
  echo "[INFO] Invite token created: $invite_token"
  echo "[INFO] To fully verify accept flow, log in as $INVITE_EMAIL and run:"
  echo "       curl -X POST \"$API_BASE/invites/$invite_token/accept\" -H \"Authorization: Bearer <INVITEE_TOKEN>\""
fi

# 6) Role update
raw="$(request PATCH "/orgs/$ORG_ID/members/$TARGET_USER_ID" "$ADMIN_TOKEN" "{\"role\":\"$PROMOTE_ROLE\"}")"
status="$(split_status "$raw" | sed -n '1p')"
body="$(split_status "$raw" | sed -n '2,$p')"
if [[ "$status" == "200" ]]; then
  updated_role="$(echo "$body" | jq -r '.role // empty')"
  if [[ "$updated_role" == "$PROMOTE_ROLE" ]]; then
    report 1 "ADMIN/OWNER can update member role"
  else
    report 0 "ADMIN/OWNER can update member role" "Expected role=$PROMOTE_ROLE, body: $body"
  fi
else
  report 0 "ADMIN/OWNER can update member role" "Expected 200, got $status, body: $body"
fi

# 7) Outsider cannot modify
raw="$(request PATCH "/orgs/$ORG_ID/members/$TARGET_USER_ID" "$OUTSIDER_TOKEN" "{\"role\":\"member\"}")"
status="$(split_status "$raw" | sed -n '1p')"
body="$(split_status "$raw" | sed -n '2,$p')"
if [[ "$status" == "403" ]]; then
  report 1 "OUTSIDER cannot update member role"
else
  report 0 "OUTSIDER cannot update member role" "Expected 403, got $status, body: $body"
fi

echo
echo "== Last-owner protections (manual, important) =="
echo "Run these manually in an org with exactly one owner:"
echo "1) Owner demote self -> expect 400"
echo "   PATCH $API_BASE/orgs/$ORG_ID/members/<OWNER_USER_ID>  {\"role\":\"admin\"}"
echo "2) Remove only owner -> expect 400"
echo "   DELETE $API_BASE/orgs/$ORG_ID/members/<OWNER_USER_ID>"
echo

echo "== Summary =="
echo "Passed: $pass_count"
echo "Failed: $fail_count"

if [[ "$fail_count" -gt 0 ]]; then
  exit 2
fi

echo "All automated checks passed."
