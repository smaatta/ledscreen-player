"""Display settings — read and write display.conf"""

import os
import re
import subprocess
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DISPLAY_CONF = os.path.join(BASE_DIR, "display.conf")


def read_conf() -> dict:
    vals = {"LED_X": 0, "LED_Y": 0, "LED_WIDTH": 768, "LED_HEIGHT": 256, "LED_OUTPUT": "HDMI-1"}
    if not os.path.exists(DISPLAY_CONF):
        return vals
    with open(DISPLAY_CONF) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key in vals:
                vals[key] = int(val) if val.isdigit() else val
    return vals


def write_conf_value(key: str, value: str):
    if not os.path.exists(DISPLAY_CONF):
        raise HTTPException(status_code=404, detail="display.conf not found")
    with open(DISPLAY_CONF) as f:
        content = f.read()
    # Replace the value in-place, preserving comments
    pattern = rf"^({re.escape(key)}\s*=\s*).*$"
    new_content = re.sub(pattern, rf"\g<1>{value}", content, flags=re.MULTILINE)
    with open(DISPLAY_CONF, "w") as f:
        f.write(new_content)


class DisplaySettings(BaseModel):
    LED_X:      int = 0
    LED_Y:      int = 0
    LED_WIDTH:  int = 768
    LED_HEIGHT: int = 256
    LED_OUTPUT: str = "HDMI-1"


@router.get("/display")
def get_display():
    return read_conf()


@router.patch("/display")
def update_display(body: DisplaySettings):
    for key, val in body.model_dump().items():
        write_conf_value(key, str(val))
    return read_conf()


@router.post("/restart-kiosk")
def restart_kiosk():
    """Kill and restart the kiosk browser so new display settings take effect."""
    try:
        subprocess.Popen(["pkill", "-f", "chromium"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}
