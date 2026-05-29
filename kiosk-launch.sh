#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# LedscreenPlayer kiosk launcher
# Positions Chromium at the exact region the Linsn SB-8 captures.
# Edit display.conf to change the capture area.
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/display.conf"

CHROMIUM=$(command -v chromium || command -v chromium-browser)

echo "[kiosk] Starting Chromium at ${LED_X},${LED_Y} size ${LED_WIDTH}x${LED_HEIGHT}"

# Launch Chromium as an app window (no browser chrome)
$CHROMIUM \
    --app=http://localhost:8000/player \
    --window-position=${LED_X},${LED_Y} \
    --window-size=${LED_WIDTH},${LED_HEIGHT} \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-features=TranslateUI \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --autoplay-policy=no-user-gesture-required \
    --check-for-update-interval=31536000 \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --hide-scrollbars \
    --overscroll-history-navigation=0 \
    --password-store=basic \
    --use-mock-keychain &

CHROMIUM_PID=$!
echo "[kiosk] Chromium PID: $CHROMIUM_PID"

# Wait for the window to appear
sleep 4

# Find the window by PID and remove its title bar decorations
WID=$(xdotool search --pid $CHROMIUM_PID 2>/dev/null | tail -1)
if [ -n "$WID" ]; then
    echo "[kiosk] Found window ID: $WID — removing decorations"
    # Remove title bar via Motif window manager hints
    xprop -id $WID -f _MOTIF_WM_HINTS 32c \
        -set _MOTIF_WM_HINTS "0x2, 0x0, 0x0, 0x0, 0x0"
    # Force exact position and size
    xdotool windowmove $WID ${LED_X} ${LED_Y}
    xdotool windowsize $WID ${LED_WIDTH} ${LED_HEIGHT}
    # Raise to top
    xdotool windowraise $WID
    echo "[kiosk] Window positioned at ${LED_X},${LED_Y} ${LED_WIDTH}x${LED_HEIGHT}"
else
    echo "[kiosk] Warning: could not find Chromium window"
fi

# Keep script alive (systemd/autostart needs the process to stay running)
wait $CHROMIUM_PID
