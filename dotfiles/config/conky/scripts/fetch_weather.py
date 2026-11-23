#!/usr/bin/env python3
"""Fetch current weather and 6-hour forecast from Open-Meteo for Conky."""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

CONFIG_PATH = "__USER_HOME__/.config/conky/scripts/config.json"
CACHE_DIR = "__USER_HOME__/.cache/liquid-glass"
JSON_OUT = os.path.join(CACHE_DIR, "weather.json")
TSV_OUT = os.path.join(CACHE_DIR, "weather.tsv")
CACHE_TTL_SEC = 900


def atomic_write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def sanitize_tsv(val):
    return str(val).replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def wmo_info(code):
    code = int(code) if code is not None else -1
    if code == 0:
        return ("快晴", "sun")
    if code in (1, 2):
        return ("晴れ", "partly")
    if code == 3:
        return ("曇り", "cloud")
    if code in (45, 48):
        return ("霧", "cloud")
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return ("雨", "rain")
    if code in (71, 73, 75, 77, 85, 86):
        return ("雪", "snow")
    if code in (95, 96, 99):
        return ("雷雨", "storm")
    return ("不明", "cloud")


def load_config():
    defaults = {
        "latitude": 35.6544,
        "longitude": 139.7447,
        "location_name": "Tokyo",
        "timezone": "Asia/Tokyo",
    }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        defaults.update({k: cfg[k] for k in defaults if k in cfg})
    except Exception:
        pass
    return defaults


def write_outputs(payload):
    atomic_write(JSON_OUT, json.dumps(payload, ensure_ascii=False, indent=2))
    lines = [
        f"location\t{sanitize_tsv(payload.get('location', 'Tokyo'))}",
        f"temp_c\t{sanitize_tsv(payload.get('temp_c', '--'))}",
        f"humidity\t{sanitize_tsv(payload.get('humidity', '--'))}",
        f"condition\t{sanitize_tsv(payload.get('condition', '--'))}",
        f"icon\t{sanitize_tsv(payload.get('icon', 'cloud'))}",
        f"updated_at\t{sanitize_tsv(payload.get('updated_at', '--'))}",
    ]
    hourly = payload.get("hourly", [])
    for idx in range(6):
        if idx < len(hourly):
            h = hourly[idx]
            lines.append(f"h{idx}_time\t{sanitize_tsv(h.get('time', '--'))}")
            lines.append(f"h{idx}_temp\t{sanitize_tsv(h.get('temp', '--'))}")
            lines.append(f"h{idx}_cond\t{sanitize_tsv(h.get('cond', '--'))}")
            lines.append(f"h{idx}_icon\t{sanitize_tsv(h.get('icon', 'cloud'))}")
            lines.append(f"h{idx}_pop\t{sanitize_tsv(h.get('pop', '0'))}")
        else:
            lines.append(f"h{idx}_time\t--")
            lines.append(f"h{idx}_temp\t--")
            lines.append(f"h{idx}_cond\t--")
            lines.append(f"h{idx}_icon\tcloud")
            lines.append(f"h{idx}_pop\t0")
    atomic_write(TSV_OUT, "\n".join(lines) + "\n")


def main():
    force = "--force" in sys.argv[1:]
    if not force and os.path.exists(JSON_OUT) and os.path.exists(TSV_OUT):
        age = time.time() - os.path.getmtime(JSON_OUT)
        if age < CACHE_TTL_SEC:
            return

    cfg = load_config()
    params = urllib.parse.urlencode({
        "latitude": cfg["latitude"],
        "longitude": cfg["longitude"],
        "current": "temperature_2m,weather_code,relative_humidity_2m",
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "timezone": cfg["timezone"],
        "forecast_days": 2,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LiquidGlassConky/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception:
        if not os.path.exists(TSV_OUT):
            write_outputs({
                "location": cfg["location_name"],
                "temp_c": "--",
                "humidity": "--",
                "condition": "オフライン",
                "icon": "cloud",
                "updated_at": "--:--",
                "hourly": [],
            })
        return

    current = raw.get("current", {})
    cur_temp = current.get("temperature_2m")
    cur_code = current.get("weather_code")
    cur_hum = current.get("relative_humidity_2m")
    cur_time_str = current.get("time", "")
    cond_label, icon_key = wmo_info(cur_code)

    hourly_data = raw.get("hourly", {})
    times = hourly_data.get("time", [])
    temps = hourly_data.get("temperature_2m", [])
    codes = hourly_data.get("weather_code", [])
    pops = hourly_data.get("precipitation_probability", [])

    cur_hour_prefix = cur_time_str[:13] + ":00" if len(cur_time_str) >= 13 else ""
    start_idx = 0
    if cur_hour_prefix:
        for i, t in enumerate(times):
            if t >= cur_hour_prefix:
                start_idx = i + 1 if t == cur_hour_prefix and i + 1 < len(times) else i
                break

    hourly_list = []
    for i in range(start_idx, min(start_idx + 6, len(times))):
        t_str = times[i]
        hhmm = t_str[11:16] if len(t_str) >= 16 else t_str
        h_temp = temps[i] if i < len(temps) and temps[i] is not None else "--"
        h_code = codes[i] if i < len(codes) else None
        h_pop = pops[i] if i < len(pops) and pops[i] is not None else 0
        h_cond, h_icon = wmo_info(h_code)
        hourly_list.append({
            "time": hhmm,
            "temp": str(round(h_temp)) if isinstance(h_temp, (int, float)) else "--",
            "cond": h_cond,
            "icon": h_icon,
            "pop": str(int(round(h_pop))) if isinstance(h_pop, (int, float)) else "0",
        })

    payload = {
        "location": cfg["location_name"],
        "temp_c": str(round(cur_temp)) if isinstance(cur_temp, (int, float)) else "--",
        "humidity": str(int(round(cur_hum))) if isinstance(cur_hum, (int, float)) else "--",
        "condition": cond_label,
        "icon": icon_key,
        "updated_at": cur_time_str[11:16] if len(cur_time_str) >= 16 else time.strftime("%H:%M"),
        "hourly": hourly_list,
    }
    write_outputs(payload)


if __name__ == "__main__":
    main()
