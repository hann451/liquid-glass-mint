#!/usr/bin/env python3
"""Collect system telemetry, YouTube/MPRIS Now Playing + album art, Gmail, and custom slots."""

import email
import email.header
import glob
import hashlib
import imaplib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

CONFIG_PATH = "__USER_HOME__/.config/conky/scripts/config.json"
CACHE_DIR = "__USER_HOME__/.cache/liquid-glass"
PREV_CPU_PATH = os.path.join(CACHE_DIR, "prev_cpu.json")
PREV_NET_PATH = os.path.join(CACHE_DIR, "prev_net.json")
GMAIL_CACHE_PATH = os.path.join(CACHE_DIR, "gmail_cache.json")
ART_HASH_PATH = os.path.join(CACHE_DIR, "album_art_url.txt")
ART_PNG_PATH = os.path.join(CACHE_DIR, "album_art.png")
JSON_OUT = os.path.join(CACHE_DIR, "status.json")
TSV_OUT = os.path.join(CACHE_DIR, "status.tsv")
GMAIL_TTL_SEC = 300


def atomic_write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def sanitize_tsv(val):
    return str(val).replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def read_cpu_percent():
    def sample():
        with open("/proc/stat", "r", encoding="utf-8") as f:
            parts = [int(x) for x in f.readline().split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
        total = sum(parts)
        return total, idle

    now_total, now_idle = sample()
    prev = None
    try:
        with open(PREV_CPU_PATH, "r", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        prev = None

    if prev is None:
        time.sleep(0.12)
        prev_total, prev_idle = now_total, now_idle
        now_total, now_idle = sample()
    else:
        prev_total = prev.get("total", 0)
        prev_idle = prev.get("idle", 0)

    atomic_write(PREV_CPU_PATH, json.dumps({"total": now_total, "idle": now_idle}))
    dt = now_total - prev_total
    di = now_idle - prev_idle
    if dt <= 0:
        return 0
    return max(0, min(100, round(100.0 * (dt - di) / dt)))


def read_cpu_temp():
    candidates = {}
    for hw in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name_file = os.path.join(hw, "name")
        if not os.path.exists(name_file):
            continue
        try:
            name = open(name_file, "r", encoding="utf-8").read().strip()
        except Exception:
            continue
        temps = sorted(glob.glob(os.path.join(hw, "temp*_input")))
        if not temps:
            continue
        try:
            milli = int(open(temps[0], "r", encoding="utf-8").read().strip())
            candidates[name] = round(milli / 1000.0)
        except Exception:
            continue

    for preferred in ("k10temp", "coretemp", "zenpower", "acpitz"):
        if preferred in candidates:
            return candidates[preferred]
    return None


def read_memory():
    info = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                k, v = line.split(":", 1)
                num = v.strip().split()[0]
                if num.isdigit():
                    info[k] = int(num)
    total_kb = info.get("MemTotal", 0)
    avail_kb = info.get("MemAvailable", info.get("MemFree", 0))
    used_kb = max(0, total_kb - avail_kb)
    pct = round(used_kb * 100.0 / total_kb) if total_kb > 0 else 0
    return {
        "percent": max(0, min(100, pct)),
        "used_gb": f"{used_kb / (1024 * 1024):.1f}",
        "total_gb": f"{total_kb / (1024 * 1024):.1f}",
    }


def read_disk():
    st = os.statvfs("/")
    total = st.f_blocks * st.f_frsize
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    avail_plus_used = (st.f_blocks - st.f_bfree + st.f_bavail) * st.f_frsize
    pct = round(used * 100.0 / avail_plus_used) if avail_plus_used > 0 else 0
    return {
        "percent": max(0, min(100, pct)),
        "used_gb": f"{used / (1024 ** 3):.0f}",
        "total_gb": f"{total / (1024 ** 3):.0f}",
    }


def read_uptime():
    try:
        secs = float(open("/proc/uptime", "r", encoding="utf-8").read().split()[0])
    except Exception:
        return "--"
    d = int(secs // 86400)
    h = int((secs % 86400) // 3600)
    m = int((secs % 3600) // 60)
    if d > 0:
        return f"{d}d {h}h"
    return f"{h}h {m}m"


def detect_active_iface():
    excluded_prefixes = ("lo", "tailscale", "docker", "veth", "br-", "virbr")
    ifaces = []
    for state_path in sorted(glob.glob("/sys/class/net/*/operstate")):
        iface = os.path.basename(os.path.dirname(state_path))
        if iface.startswith(excluded_prefixes):
            continue
        try:
            state = open(state_path, "r", encoding="utf-8").read().strip().lower()
        except Exception:
            state = ""
        if state == "up":
            ifaces.append(iface)
    if ifaces:
        return ifaces[0]
    for state_path in sorted(glob.glob("/sys/class/net/*/operstate")):
        iface = os.path.basename(os.path.dirname(state_path))
        if not iface.startswith(excluded_prefixes):
            return iface
    return "offline"


def read_network():
    iface = detect_active_iface()
    rx_bytes = 0
    tx_bytes = 0
    if iface != "offline":
        with open("/proc/net/dev", "r", encoding="utf-8") as f:
            for line in f.readlines()[2:]:
                if ":" not in line:
                    continue
                name, rest = line.split(":", 1)
                if name.strip() == iface:
                    cols = rest.split()
                    rx_bytes = int(cols[0])
                    tx_bytes = int(cols[8])
                    break

    now = time.time()
    down_kbps = 0.0
    up_kbps = 0.0
    try:
        prev = json.load(open(PREV_NET_PATH, "r", encoding="utf-8"))
        if prev.get("iface") == iface:
            dt = max(0.2, now - prev.get("ts", now))
            drx = max(0, rx_bytes - prev.get("rx", rx_bytes))
            dtx = max(0, tx_bytes - prev.get("tx", tx_bytes))
            down_kbps = (drx / 1024.0) / dt
            up_kbps = (dtx / 1024.0) / dt
    except Exception:
        pass

    atomic_write(PREV_NET_PATH, json.dumps({
        "iface": iface,
        "rx": rx_bytes,
        "tx": tx_bytes,
        "ts": now,
    }))

    def fmt_rate(kbps):
        if kbps >= 1024.0:
            return f"{kbps / 1024.0:.1f} MB/s"
        return f"{kbps:.0f} KB/s"

    return {
        "iface": iface,
        "down_str": fmt_rate(down_kbps),
        "up_str": fmt_rate(up_kbps),
    }


def prepare_album_art(art_url):
    if not art_url:
        return False
    os.makedirs(CACHE_DIR, exist_ok=True)
    url_hash = hashlib.sha256(art_url.encode("utf-8")).hexdigest()
    try:
        if os.path.exists(ART_HASH_PATH) and os.path.exists(ART_PNG_PATH):
            old_hash = open(ART_HASH_PATH, "r", encoding="utf-8").read().strip()
            if old_hash == url_hash:
                return True
    except Exception:
        pass

    raw_bytes = None
    try:
        if art_url.startswith("file://"):
            local_path = urllib.parse.unquote(art_url[7:])
            with open(local_path, "rb") as f:
                raw_bytes = f.read()
        elif os.path.exists(art_url):
            with open(art_url, "rb") as f:
                raw_bytes = f.read()
        elif art_url.startswith(("http://", "https://")):
            req = urllib.request.Request(art_url, headers={"User-Agent": "LiquidGlassConky/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                raw_bytes = resp.read()
    except Exception:
        return os.path.exists(ART_PNG_PATH)

    if not raw_bytes:
        return False

    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        loader = GdkPixbuf.PixbufLoader()
        loader.write(raw_bytes)
        loader.close()
        pixbuf = loader.get_pixbuf()
        if pixbuf is None:
            return False
        w = pixbuf.get_width()
        h = pixbuf.get_height()
        side = min(w, h)
        if side <= 0:
            return False
        cropped = pixbuf.new_subpixbuf((w - side) // 2, (h - side) // 2, side, side)
        scaled = cropped.scale_simple(64, 64, GdkPixbuf.InterpType.BILINEAR)
        tmp_png = f"{ART_PNG_PATH}.tmp.{os.getpid()}.png"
        scaled.savev(tmp_png, "png", [], [])
        os.replace(tmp_png, ART_PNG_PATH)
        atomic_write(ART_HASH_PATH, url_hash)
        return True
    except Exception:
        return False


def read_now_playing():
    idle_result = {
        "status": "idle",
        "artist": "Chrome再生と自動連携",
        "title": "YouTube で再生",
        "progress": 0.0,
        "art_ready": False,
    }
    if not shutil.which("playerctl"):
        return idle_result
    try:
        res = subprocess.run(
            [
                "playerctl", "-a", "metadata", "--format",
                "{{playerName}}\t{{status}}\t{{artist}}\t{{title}}\t{{mpris:artUrl}}\t{{position}}\t{{mpris:length}}",
            ],
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        out = res.stdout.strip()
        if res.returncode != 0 or not out:
            return idle_result

        candidates = []
        for line in out.splitlines():
            cols = line.split("\t")
            while len(cols) < 7:
                cols.append("")
            pname, st, artist, title, art_url, pos_s, len_s = [c.strip() for c in cols[:7]]
            if not title:
                continue
            st_l = st.lower()
            is_playing = 1 if st_l == "playing" else 0
            is_paused = 1 if st_l == "paused" else 0
            if not is_playing and not is_paused:
                continue
            is_browser = 1 if any(b in pname.lower() for b in ("chrom", "brave", "firefox", "edge")) else 0
            is_yt = 1 if ("youtube" in title.lower() or "ytimg" in art_url.lower()) else 0
            candidates.append(((is_playing, is_yt, is_browser), pname, st_l, artist, title, art_url, pos_s, len_s))

        if not candidates:
            return idle_result

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, pname, st_l, artist, title, art_url, pos_s, len_s = candidates[0]

        clean_title = re.sub(r"\s*[-–|]\s*YouTube(\s+Music)?$", "", title, flags=re.IGNORECASE).strip() or title
        if not artist:
            artist = "YouTube" if any(b in pname.lower() for b in ("chrom", "brave", "firefox", "edge")) else pname

        progress = 0.0
        try:
            pos_v = int(pos_s)
            len_v = int(len_s)
            if len_v > 0 and pos_v >= 0:
                progress = max(0.0, min(1.0, pos_v / float(len_v)))
        except Exception:
            progress = 0.0

        art_ready = prepare_album_art(art_url) if art_url else False
        return {
            "status": st_l,
            "artist": artist,
            "title": clean_title,
            "progress": round(progress, 3),
            "art_ready": art_ready,
        }
    except Exception:
        return idle_result


def decode_mime(val):
    if not val:
        return ""
    chunks = []
    for part, enc in email.header.decode_header(val):
        if isinstance(part, bytes):
            chunks.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            chunks.append(part)
    return "".join(chunks).strip()


def read_gmail(cfg):
    gmail_cfg = cfg.get("gmail", {})
    enabled = bool(gmail_cfg.get("enabled", False))
    addr = str(gmail_cfg.get("email", "")).strip()
    pw_file = str(gmail_cfg.get("app_password_file", "")).strip()
    server = str(gmail_cfg.get("imap_server", "imap.gmail.com")).strip() or "imap.gmail.com"

    if not enabled or not addr or not pw_file or not os.path.exists(pw_file):
        return {"configured": False, "unread": 0, "subjects": []}

    pw = open(pw_file, "r", encoding="utf-8").read().strip()
    if not pw:
        return {"configured": False, "unread": 0, "subjects": []}

    if os.path.exists(GMAIL_CACHE_PATH):
        if time.time() - os.path.getmtime(GMAIL_CACHE_PATH) < GMAIL_TTL_SEC:
            try:
                return json.load(open(GMAIL_CACHE_PATH, "r", encoding="utf-8"))
            except Exception:
                pass

    result = {"configured": True, "unread": 0, "subjects": []}
    try:
        mail = imaplib.IMAP4_SSL(server, timeout=8)
        mail.login(addr, pw)
        mail.select("INBOX", readonly=True)
        _, unseen_data = mail.search(None, "UNSEEN")
        unseen_ids = unseen_data[0].split() if unseen_data and unseen_data[0] else []
        result["unread"] = len(unseen_ids)

        target_ids = unseen_ids[-3:] if unseen_ids else []
        if not target_ids:
            _, all_data = mail.search(None, "ALL")
            all_ids = all_data[0].split() if all_data and all_data[0] else []
            target_ids = all_ids[-3:]

        subjects = []
        for msg_id in reversed(target_ids):
            _, msg_data = mail.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            raw_hdr = msg_data[0][1] if msg_data and isinstance(msg_data[0], tuple) else b""
            msg = email.message_from_bytes(raw_hdr)
            subj = decode_mime(msg.get("Subject", "(件名なし)")) or "(件名なし)"
            frm = decode_mime(msg.get("From", ""))
            sender = frm.split("<")[0].strip().strip('"') or frm
            subjects.append(f"{sender}: {subj}" if sender else subj)

        result["subjects"] = subjects
        mail.close()
        mail.logout()
        atomic_write(GMAIL_CACHE_PATH, json.dumps(result, ensure_ascii=False))
    except Exception:
        if os.path.exists(GMAIL_CACHE_PATH):
            try:
                return json.load(open(GMAIL_CACHE_PATH, "r", encoding="utf-8"))
            except Exception:
                pass
    return result


def read_custom_slots(cfg):
    path = cfg.get("custom_json_path", "")
    if not path or not os.path.exists(path):
        return []
    try:
        raw = json.load(open(path, "r", encoding="utf-8"))
        items = raw.get("items", []) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return []
        cleaned = []
        for item in items[:2]:
            if isinstance(item, dict):
                lbl = str(item.get("label", "")).strip()
                val = str(item.get("value", "")).strip()
                if lbl or val:
                    cleaned.append({"label": lbl, "value": val})
        return cleaned
    except Exception:
        return []


def main():
    cfg = load_config()
    cpu_pct = read_cpu_percent()
    cpu_temp = read_cpu_temp()
    mem = read_memory()
    disk = read_disk()
    uptime = read_uptime()
    net = read_network()
    media = read_now_playing()
    gmail = read_gmail(cfg)
    custom = read_custom_slots(cfg)

    payload = {
        "cpu_pct": cpu_pct,
        "cpu_temp": cpu_temp,
        "mem": mem,
        "disk": disk,
        "uptime": uptime,
        "net": net,
        "media": media,
        "gmail": gmail,
        "custom": custom,
    }
    atomic_write(JSON_OUT, json.dumps(payload, ensure_ascii=False, indent=2))

    lines = [
        f"cpu_pct\t{cpu_pct}",
        f"cpu_temp\t{cpu_temp if cpu_temp is not None else '--'}",
        f"mem_pct\t{mem['percent']}",
        f"mem_used\t{mem['used_gb']}",
        f"mem_total\t{mem['total_gb']}",
        f"disk_pct\t{disk['percent']}",
        f"disk_used\t{disk['used_gb']}",
        f"disk_total\t{disk['total_gb']}",
        f"uptime\t{sanitize_tsv(uptime)}",
        f"net_iface\t{sanitize_tsv(net['iface'])}",
        f"net_down\t{sanitize_tsv(net['down_str'])}",
        f"net_up\t{sanitize_tsv(net['up_str'])}",
        f"media_status\t{sanitize_tsv(media['status'])}",
        f"media_artist\t{sanitize_tsv(media['artist'])}",
        f"media_title\t{sanitize_tsv(media['title'])}",
        f"media_progress\t{media['progress']}",
        f"media_art_ready\t{'1' if media['art_ready'] else '0'}",
        f"gmail_configured\t{'1' if gmail['configured'] else '0'}",
        f"gmail_unread\t{gmail['unread']}",
    ]
    for i in range(3):
        subj = gmail["subjects"][i] if i < len(gmail["subjects"]) else ""
        lines.append(f"gmail_m{i}\t{sanitize_tsv(subj)}")
    lines.append(f"custom_count\t{len(custom)}")
    for i in range(2):
        if i < len(custom):
            lines.append(f"custom{i}_label\t{sanitize_tsv(custom[i]['label'])}")
            lines.append(f"custom{i}_value\t{sanitize_tsv(custom[i]['value'])}")
        else:
            lines.append(f"custom{i}_label\t")
            lines.append(f"custom{i}_value\t")

    atomic_write(TSV_OUT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
