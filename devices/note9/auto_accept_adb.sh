#!/bin/bash
# auto_accept_adb.sh
# Accept USB debugging dialog on Samsung phone with broken/unresponsive screen
# Uses scrcpy OTG (AOA HID protocol) — no ADB authorization needed
#
# Workflow:
#   1. Start scrcpy --otg (keyboard+mouse HID over USB, no ADB required)
#   2. Send Home key to dismiss any foreground app
#   3. Blind-click at known positions of the "Allow USB debugging?" dialog
#   4. Verify ADB authorization succeeded
#
# Dependencies: adb, scrcpy (with libusb), xdotool
# Requires: X11 display (DISPLAY must be set)

set -euo pipefail

# ─── Configuración ────────────────────────────────────────────────────────────

SERIAL="${1:-29396e8c1e3f7ece}"
TIMEOUT="${2:-30}"               # max seconds to try
TRIES=6                          # attempts per round

ADB="${ADB:-adb}"
LOG="${LOG:-/tmp/adb_auto_accept.log}"

# ─── Helpers ─────────────────────────────────────────────────────────────────

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
die()  { log "FATAL: $*"; exit 1; }

# ─── State helpers ────────────────────────────────────────────────────────────

is_authorized() {
  local state
  state=$($ADB devices 2>/dev/null | awk -v s="$SERIAL" '$1==s {print $2}')
  [ "$state" = "device" ]
}

wait_unauthorized() {
  # Wait for device to appear in adb (any state)
  for i in $(seq 1 15); do
    $ADB devices 2>/dev/null | grep -q "$SERIAL" && return 0
    sleep 1
  done
  return 1
}

# ─── HID actions via scrcpy OTG window ────────────────────────────────────────

start_otg() {
  local pid_file="$1"

  # Kill leftover scrcpy
  pkill -f "scrcpy.*--otg" 2>/dev/null || true
  sleep 1

  # Start scrcpy OTG in background
  scrcpy --otg 2>>"$LOG" &
  local pid=$!
  echo "$pid" > "$pid_file"

  # Wait for its window to appear
  for i in $(seq 1 12); do
    WID=$(xdotool search --name "SAMSUNG_Android" 2>/dev/null | head -1)
    [ -n "$WID" ] && { echo "$WID"; return 0; }
    sleep 1
  done
  return 1
}

hid_tap() {
  local window_id="$1" pct_x="$2" pct_y="$3"
  eval "$(xdotool getwindowgeometry --shell "$window_id" 2>/dev/null)" || return 1
  xdotool mousemove --window "$window_id" $((WIDTH * pct_x / 100)) $((HEIGHT * pct_y / 100)) 2>/dev/null
  sleep 0.2
  xdotool click --window "$window_id" 1 2>/dev/null
}

hid_key() {
  local window_id="$1" key="$2"
  xdotool key --window "$window_id" "$key" 2>/dev/null
}

# ─── Click strategies ─────────────────────────────────────────────────────────
# Positions are % of window width/height.
# scrcpy OTG scales window-relative coords to phone screen.

# Primary: the "Permitir" / "Allow" button position we empirically found
ALLOW_BUTTON=(68 85)

# Additional candidates (common Samsung USB dialog positions)
ALLOW_CANDIDATES=(
  "68 85"
  "75 90"
  "50 88"
  "70 88"
  "80 90"
  "60 80"
  "65 92"
  "55 82"
)

# Checkbox "Always allow" area
CHECKBOX=(40 78)

# ─── Main ─────────────────────────────────────────────────────────────────────

main() {
  # Check dependencies
  command -v "$ADB"    >/dev/null || die "adb not found"
  command -v scrcpy    >/dev/null || die "scrcpy not found"
  command -v xdotool   >/dev/null || die "xdotool not found (install: sudo apt install xdotool)"
  [ -n "${DISPLAY:-}" ]           || die "DISPLAY not set (no X11)"

  log "=== ADB auto-accept for $SERIAL ==="

  # Already authorized?
  if is_authorized; then
    log "Device already authorized"
    exit 0
  fi

  # Wait for device to appear on USB
  wait_unauthorized || die "Device $SERIAL not found via adb"

  log "Device detected (unauthorized). Starting scrcpy OTG..."

  # Start OTG
  PID_FILE=$(mktemp)
  WID=$(start_otg "$PID_FILE") || die "Failed to start scrcpy OTG or find its window"
  OTG_PID=$(cat "$PID_FILE")
  log "scrcpy OTG running (PID=$OTG_PID, window=$WID)"

  # Phase 1: Send Home key to dismiss apps that might block dialog
  log "Sending Home key..."
  hid_key "$WID" Home
  sleep 1

  # Check if Home already did the trick
  if is_authorized; then
    log "AUTHORIZED after Home key!"
    kill "$OTG_PID" 2>/dev/null; exit 0
  fi

  # Phase 2: Try clicking the dialog
  log "Attempting to accept USB debugging dialog..."

  for round in $(seq 1 "$TRIES"); do
    for pos in "${ALLOW_CANDIDATES[@]}"; do
      if is_authorized; then
        log "AUTHORIZED at round $round!"
        kill "$OTG_PID" 2>/dev/null; exit 0
      fi

      px="${pos%% *}"
      py="${pos##* }"
      log "  $round: tap ${px}% ${py}%"
      hid_tap "$WID" "$px" "$py"
      sleep 1
    done

    # Also try checkbox+Allow sequence
    if ! is_authorized; then
      log "  $round: checkbox+Allow sequence"
      hid_tap "$WID" "${CHECKBOX[0]}" "${CHECKBOX[1]}"
      sleep 0.4
      hid_tap "$WID" "${ALLOW_BUTTON[0]}" "${ALLOW_BUTTON[1]}"
      sleep 1
    fi

    # If still not authorized, reset ADB to re-trigger dialog
    if ! is_authorized; then
      log "  $round: re-triggering ADB authorization..."
      $ADB kill-server 2>/dev/null || true
      sleep 1
      $ADB start-server 2>/dev/null || true
      sleep 3
    fi
  done

  # Cleanup
  kill "$OTG_PID" 2>/dev/null || true
  rm -f "$PID_FILE"

  if is_authorized; then
    log "=== SUCCESS: Device authorized ==="
    exit 0
  else
    log "=== FAILED: Device still unauthorized ==="
    log "Try: disconnect/reconnect USB cable, then run this script again"
    log "Or connect a USB mouse via OTG adapter and click bottom-right of phone screen"
    exit 1
  fi
}

main "$@"
