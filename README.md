# LedscreenPlayer

Digital signage player for **Raspberry Pi + Linsn SB-8** LED sender box.

## Architecture

```
Raspberry Pi
├── FastAPI backend  (port 8000)
│   ├── REST API — media, playlists, schedules, player control
│   ├── WebSocket — real-time push to kiosk browser
│   └── SQLite database
│
├── Chromium (kiosk mode, full-screen → HDMI out)
│   └── http://localhost:8000/player
│
└── Management UI
    └── http://<pi-ip>:8000  (any browser on local network)

Linsn SB-8
└── receives HDMI signal from Pi → drives LED panels
```

> **Display setup note:** The SB-8 is configured as a **secondary mirrored monitor** in the upper-right region of the extended desktop. The kiosk window is positioned and sized to exactly cover that region — so whatever the player renders there is captured and sent to the LED wall.

## Quick install (Raspberry Pi OS)

```bash
git clone https://github.com/yourname/ledscreen-player.git
cd ledscreen-player
chmod +x install.sh
./install.sh
```

After install, reboot:
```bash
sudo reboot
```

## Manual start (development)

```bash
cd ledscreen-player
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Access

| URL | Purpose |
|-----|---------|
| `http://<pi-ip>:8000` | Management UI |
| `http://<pi-ip>:8000/player` | Fullscreen player |
| `http://<pi-ip>:8000/docs` | Swagger API docs |

## LED screen region setup

Since the Linsn SB-8 captures a specific region of the desktop, position the player window to match exactly:

1. Open `services/ledplayer-kiosk.service`
2. Add `--window-position=X,Y --window-size=W,H` to the Chromium flags
   (where X,Y is the top-left of your LED region, W×H is the panel resolution)
3. Remove `--kiosk` and add `--start-fullscreen` if you want windowed positioning

**Example** for a 1920×1080 panel starting at x=1920 (right of main display):
```
--window-position=1920,0 --window-size=1920,1080 --start-fullscreen
```

## Supported content

| Type | Formats |
|------|---------|
| Images | JPG, PNG, GIF (animated), WebP |
| Video | MP4, WebM, MOV |
| Clock widget | Digital clock with optional date |
| Weather widget | OpenWeatherMap live data |
| Text ticker | Scrolling or static message |
| RSS widget | Live headlines from any RSS feed |

## Services

```bash
# Status
sudo systemctl status ledplayer-api
sudo systemctl status ledplayer-kiosk

# Logs
sudo journalctl -u ledplayer-api -f
sudo journalctl -u ledplayer-kiosk -f

# Restart
sudo systemctl restart ledplayer-api
sudo systemctl restart ledplayer-kiosk
```
