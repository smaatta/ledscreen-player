#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# LedscreenPlayer kiosk launcher
# Uses --kiosk for full-screen (removes taskbar and title bar)
# Player HTML constrains content to the SB-8 capture area (top-left corner)
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/display.conf"

CHROMIUM=$(command -v chromium || command -v chromium-browser)

echo "[kiosk] Starting in kiosk mode, content area: ${LED_WIDTH}x${LED_HEIGHT}"

# Hide mouse cursor using unclutter
unclutter -idle 0 -root &

exec $CHROMIUM \
    --kiosk \
    --app="http://localhost:8000/player?w=${LED_WIDTH}&h=${LED_HEIGHT}" \
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
    --use-mock-keychain
