#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# LedscreenPlayer — Raspberry Pi install script
# Tested on: Raspberry Pi OS (Bookworm / Bullseye), Pi 4 / Pi 5
# Usage:  chmod +x install.sh && ./install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

INSTALL_DIR="/home/pi/ledscreen-player"
SERVICE_USER="pi"
PYTHON="python3"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] && die "Do not run as root. Run as the 'pi' user."

# ── 1. System packages ───────────────────────────────────────────────────────
info "Updating package list…"
sudo apt-get update -qq

info "Installing system dependencies…"

# Detect correct Chromium package name (Bookworm uses 'chromium', older uses 'chromium-browser')
if apt-cache show chromium &>/dev/null 2>&1; then
    CHROMIUM_PKG="chromium"
else
    CHROMIUM_PKG="chromium-browser"
fi
info "Using Chromium package: $CHROMIUM_PKG"

# libgl1-mesa-glx was renamed to libgl1 in Bookworm
if apt-cache show libgl1-mesa-glx &>/dev/null 2>&1; then
    GL_PKG="libgl1-mesa-glx"
else
    GL_PKG="libgl1"
fi

sudo apt-get install -y -qq \
    python3 python3-pip python3-venv \
    $CHROMIUM_PKG \
    $GL_PKG \
    ffmpeg \
    xdotool \
    unclutter \
    git

ok "System packages installed."

# ── 2. Copy project files ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    info "Copying project to $INSTALL_DIR…"
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR"/. "$INSTALL_DIR/"
fi

cd "$INSTALL_DIR"

# ── 3. Python virtual environment ────────────────────────────────────────────
info "Creating Python virtual environment…"
$PYTHON -m venv .venv
source .venv/bin/activate

info "Installing Python dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Python environment ready."

# ── 4. Data & media directories ──────────────────────────────────────────────
info "Creating runtime directories…"
mkdir -p data media/uploads media/thumbnails
ok "Directories created."

# ── 5. Disable screen blanking ───────────────────────────────────────────────
info "Disabling screen saver / blanking…"
XSCREENSAVER_CFG="/home/pi/.xscreensaver"
cat > "$XSCREENSAVER_CFG" << 'EOF'
mode:		off
lock:		False
dpmsEnabled:	False
EOF

# Also via xset (takes effect at next X session)
if command -v xset &>/dev/null; then
    export DISPLAY=:0 2>/dev/null || true
    xset s off 2>/dev/null || true
    xset -dpms 2>/dev/null || true
    xset s noblank 2>/dev/null || true
fi

# Boot config
BOOT_CFG="/boot/firmware/config.txt"
[ -f /boot/config.txt ] && BOOT_CFG="/boot/config.txt"
if ! grep -q "blanking=1" "$BOOT_CFG" 2>/dev/null; then
    warn "Add 'blanking=1' to $BOOT_CFG manually if needed for your display."
fi

ok "Screen blanking disabled."

# ── 6. Hide mouse cursor (unclutter) ─────────────────────────────────────────
AUTOSTART_DIR="/home/pi/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/unclutter.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=unclutter
Exec=unclutter -idle 0.5 -root
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

ok "Mouse cursor will be hidden in kiosk mode."

# ── 6b. Detect LED display region ────────────────────────────────────────────
info "Detecting display configuration…"

# Try to auto-detect the secondary output position from xrandr
XRANDR_OUT=""
if command -v xrandr &>/dev/null && [ -n "${DISPLAY:-}" ]; then
    XRANDR_OUT=$(DISPLAY=:0 xrandr --query 2>/dev/null || true)
fi

if [ -n "$XRANDR_OUT" ]; then
    info "Detected outputs:"
    echo "$XRANDR_OUT" | grep " connected" | awk '{print "  "$0}'
    warn "Edit ${INSTALL_DIR}/display.conf to set LED_X, LED_Y, LED_WIDTH, LED_HEIGHT"
    warn "to match the region the Linsn SB-8 captures on the extended desktop."
    warn "Run 'xrandr --query' to find the offset/size of the secondary output."
else
    warn "Could not query xrandr. Edit ${INSTALL_DIR}/display.conf manually after install."
fi

# ── 7. Systemd services ───────────────────────────────────────────────────────
info "Installing systemd services…"

# Patch service files with actual install dir & user
sed "s|/home/pi/ledscreen-player|$INSTALL_DIR|g; s|User=pi|User=$SERVICE_USER|g" \
    services/ledplayer-api.service | sudo tee /etc/systemd/system/ledplayer-api.service > /dev/null

# Kiosk service: patch path and also update the display.conf reference
sed "s|/home/pi/ledscreen-player|$INSTALL_DIR|g; s|User=pi|User=$SERVICE_USER|g" \
    services/ledplayer-kiosk.service | sudo tee /etc/systemd/system/ledplayer-kiosk.service > /dev/null

info "Edit ${INSTALL_DIR}/display.conf to set your LED panel position and resolution."
info "Then run: sudo systemctl restart ledplayer-kiosk"

sudo systemctl daemon-reload
sudo systemctl enable ledplayer-api.service
sudo systemctl enable ledplayer-kiosk.service

ok "Services installed and enabled."

# ── 8. Start services now ────────────────────────────────────────────────────
info "Starting API server…"
sudo systemctl start ledplayer-api.service
sleep 2

if sudo systemctl is-active --quiet ledplayer-api.service; then
    ok "API server is running."
else
    warn "API server may not have started yet. Check: sudo journalctl -u ledplayer-api -n 50"
fi

# ── 9. Network info ───────────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✔  LedscreenPlayer installed successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Management UI  →  ${CYAN}http://${LOCAL_IP}:8000${NC}"
echo -e "  Player screen  →  ${CYAN}http://${LOCAL_IP}:8000/player${NC}"
echo -e "  API docs       →  ${CYAN}http://${LOCAL_IP}:8000/docs${NC}"
echo ""
echo -e "  Service commands:"
echo -e "    sudo systemctl status ledplayer-api"
echo -e "    sudo journalctl -u ledplayer-api -f"
echo -e "    sudo journalctl -u ledplayer-kiosk -f"
echo ""
echo -e "  Reboot to start the kiosk browser automatically."
echo ""
