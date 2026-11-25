#!/usr/bin/env python3
"""Manage unlimited desktop embedded web/app widgets from widgets.json."""

import glob
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
WIDGETS_DIR = os.path.join(HOME, ".config", "desktop-widgets")
CONFIG_PATH = os.path.join(WIDGETS_DIR, "widgets.json")
DEVILSPIE_LUA = os.path.join(HOME, ".config", "devilspie2", "desktop_widgets.lua")
BLUR_JSON = os.path.join(
    HOME, ".config", "cinnamon", "spices", "BlurCinnamon@klangman", "BlurCinnamon@klangman.json"
)
APPS_DIR = os.path.join(HOME, ".local", "share", "applications")
PLANK_LAUNCHERS_DIR = os.path.join(HOME, ".config", "plank", "dock1", "launchers")
LOG_DIR = os.path.join(HOME, ".cache", "liquid-glass")
LEGACY_CLASSES = {"DesktopNotion", "DesktopMiniWeb", "DesktopWidget2", "DesktopWidget3"}


def ensure_display_env():
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    return env


def detect_browser():
    for cand in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "brave-browser"):
        path = shutil.which(cand)
        if path:
            return path
    return None


def get_screen_size(env):
    try:
        out = subprocess.check_output(["xrandr", "--current"], env=env, text=True, timeout=3)
        m = re.search(r"connected primary (\d+)x(\d+)\+", out)
        if m:
            return int(m.group(1)), int(m.group(2))
        m2 = re.search(r"\b(\d+)x(\d+)\s+\d+\.\d+\*", out)
        if m2:
            return int(m2.group(1)), int(m2.group(2))
    except Exception:
        pass
    return 1920, 1080


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"slots": []}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def resolve_slot_geom(slot, screen_w, screen_h):
    w = max(200, min(screen_w - 20, int(slot.get("width", 480))))
    h = max(160, min(screen_h - 40, int(slot.get("height", 400))))
    if slot.get("align_right", True):
        margin = max(0, int(slot.get("right_margin", 32)))
        x = max(0, screen_w - w - margin)
    else:
        x = max(0, min(screen_w - w, int(slot.get("x", 360))))
    y = max(28, min(screen_h - h, int(slot.get("y", 52))))
    opacity = max(50, min(100, int(slot.get("opacity", 88))))
    corner = max(0, min(25, int(slot.get("corner_radius", 20))))
    return x, y, w, h, opacity, corner


def widget_desktop_path(slot_id):
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", slot_id)
    return os.path.join(APPS_DIR, f"desktop-widget-{safe}.desktop")


def sync_hidden_desktop_files(slots):
    os.makedirs(APPS_DIR, exist_ok=True)
    active_files = set()
    for slot in slots:
        if slot.get("type", "web") != "web":
            continue
        wm_class = str(slot.get("wm_class", "")).strip()
        if not wm_class:
            continue
        df = widget_desktop_path(slot["id"])
        active_files.add(df)
        content = "\n".join([
            "[Desktop Entry]",
            "Type=Application",
            f"Name=Desktop Widget ({slot.get('name', slot['id'])})",
            f"Exec={os.path.join(HOME, '.local', 'bin', 'launch-desktop-widgets.sh')} --focus {slot['id']}",
            f"StartupWMClass={wm_class}",
            "NoDisplay=true",
            "Terminal=false",
            "",
        ])
        with open(df, "w", encoding="utf-8") as f:
            f.write(content)

    for stale in glob.glob(os.path.join(APPS_DIR, "desktop-widget-*.desktop")):
        if stale not in active_files:
            try:
                os.remove(stale)
            except OSError:
                pass


def sync_plank_dock_pins(slots):
    """Remove unused notion/timetree dockitems and keep only pin_to_dock=true widget items."""
    if not shutil.which("plank"):
        return
    try:
        cur_raw = subprocess.check_output(
            ["dconf", "read", "/net/launchpad/plank/docks/dock1/dock-items"],
            text=True,
            timeout=2,
        ).strip()
    except Exception:
        return

    # Parse dconf string list e.g. ['a.dockitem', 'b.dockitem']
    cur_items = re.findall(r"'([^']+)'", cur_raw)
    if not cur_items:
        return

    # Legacy widget dockitems to clean up unless explicitly pinned
    legacy_widget_items = {"07-notion.dockitem", "08-timetree.dockitem", "08-gmail.dockitem"}
    pinned_map = {}
    for slot in slots:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", slot["id"])
        fname = f"w-{safe}.dockitem"
        if slot.get("enabled", False) and slot.get("pin_to_dock", False):
            pinned_map[fname] = slot

    changed = False
    new_items = []
    for item in cur_items:
        if item in legacy_widget_items or (item.startswith("w-") and item.endswith(".dockitem") and item not in pinned_map):
            p = os.path.join(PLANK_LAUNCHERS_DIR, item)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
            changed = True
            continue
        new_items.append(item)

    for fname, slot in pinned_map.items():
        if fname not in new_items:
            df = widget_desktop_path(slot["id"]) if slot.get("type", "web") == "web" else slot.get("desktop_file", "")
            if df and os.path.exists(df):
                os.makedirs(PLANK_LAUNCHERS_DIR, exist_ok=True)
                with open(os.path.join(PLANK_LAUNCHERS_DIR, fname), "w", encoding="utf-8") as f:
                    f.write(f"[PlankDockItemPreferences]\nLauncher=file://{df}\n")
                insert_pos = max(0, len(new_items) - 2)
                new_items.insert(insert_pos, fname)
                changed = True

    if changed:
        subprocess.run(["pkill", "-x", "plank"], stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        dconf_val = "[" + ", ".join(f"'{i}'" for i in new_items) + "]"
        subprocess.run(["dconf", "write", "/net/launchpad/plank/docks/dock1/dock-items", dconf_val], check=False)
        os.makedirs(LOG_DIR, exist_ok=True)
        env = ensure_display_env()
        with open(os.path.join(LOG_DIR, "plank.log"), "ab") as logf:
            subprocess.Popen(["plank"], env=env, stdout=logf, stderr=logf, start_new_session=True)


def sync_configs(restart_devilspie=True, update_plank=True, env=None):
    if env is None:
        env = ensure_display_env()
    cfg = load_config()
    slots = cfg.get("slots", [])
    screen_w, screen_h = get_screen_size(env)

    sync_hidden_desktop_files(slots)

    # 1. Generate Devilspie2 Lua rules
    os.makedirs(os.path.dirname(DEVILSPIE_LUA), exist_ok=True)
    lua_lines = [
        "-- Auto-generated by desktop-widgets-manager.py from widgets.json",
        'local cls = string.lower(get_window_class() or "")',
        'local inst = string.lower(get_class_instance_name() or "")',
        "",
    ]
    for slot in slots:
        if not slot.get("enabled", False):
            continue
        wm_class = str(slot.get("wm_class", "")).strip()
        if not wm_class:
            continue
        x, y, w, h, opacity, _ = resolve_slot_geom(slot, screen_w, screen_h)
        op_float = f"{opacity / 100.0:.2f}"
        lc = wm_class.lower()
        lua_lines.extend([
            f'if (cls == "{lc}" or inst == "{lc}") then',
            "    undecorate_window()",
            f"    set_window_geometry2({x}, {y}, {w}, {h})",
            "    set_window_below(true)",
            "    stick_window()",
            "    pin_window()",
            "    set_skip_tasklist(true)",
            "    set_skip_pager(true)",
            f"    set_window_opacity({op_float})",
            "end",
            "",
        ])
    with open(DEVILSPIE_LUA, "w", encoding="utf-8") as f:
        f.write("\n".join(lua_lines))

    # 2. Update BlurCinnamon inclusion list
    if os.path.exists(BLUR_JSON):
        try:
            with open(BLUR_JSON, "r", encoding="utf-8") as f:
                blur_data = json.load(f)
            if "enable-window-effects" in blur_data:
                blur_data["enable-window-effects"]["value"] = True
            inc = blur_data.get("windows-inclusion-list", {}).get("value", [])
            managed_names = LEGACY_CLASSES | {str(s.get("wm_class", "")) for s in slots}
            inc = [item for item in inc if item.get("application") not in managed_names]
            new_entries = []
            for slot in slots:
                if not slot.get("enabled", False):
                    continue
                wm_class = str(slot.get("wm_class", "")).strip()
                if not wm_class:
                    continue
                _, _, _, _, opacity, corner = resolve_slot_geom(slot, screen_w, screen_h)
                new_entries.append({
                    "enabled": True,
                    "application": wm_class,
                    "window_opacity": opacity,
                    "override": True,
                    "opacity": 15,
                    "color": "rgb(18,22,32)",
                    "blurtype": 8,
                    "radius": 14,
                    "saturation": 100,
                    "corner_radius": corner,
                    "corner_top": True,
                    "corner_bottom": True,
                })
            if "windows-inclusion-list" in blur_data:
                blur_data["windows-inclusion-list"]["value"] = new_entries + inc
            with open(BLUR_JSON, "w", encoding="utf-8") as f:
                json.dump(blur_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: BlurCinnamon update failed: {e}", file=sys.stderr)

    # 3. Reload Devilspie2 if requested
    if restart_devilspie and shutil.which("devilspie2"):
        subprocess.run(["pkill", "-x", "devilspie2"], stderr=subprocess.DEVNULL)
        time.sleep(0.3)
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "devilspie2.log"), "ab") as logf:
            subprocess.Popen(["devilspie2"], env=env, stdout=logf, stderr=logf, start_new_session=True)

    # 4. Sync Plank dock pins cleanly
    if update_plank:
        sync_plank_dock_pins(slots)


def find_wid(wm_class, env):
    if not wm_class:
        return None
    try:
        out = subprocess.check_output(["wmctrl", "-lx"], env=env, text=True, timeout=3)
        pat = wm_class.lower()
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 3 and pat in parts[2].lower():
                return parts[0]
    except Exception:
        pass
    return None


def get_running_profile_url(profile_dir):
    needle = f"--user-data-dir={profile_dir}"
    for pid_str in os.listdir("/proc"):
        if not pid_str.isdigit():
            continue
        try:
            raw = open(f"/proc/{pid_str}/cmdline", "rb").read()
            cmd = raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore")
            if needle in cmd and "--type=" not in cmd and any(b in cmd for b in ("chrome", "chromium", "brave")):
                m = re.search(r"--app=(\S+)", cmd)
                return m.group(1) if m else "__RUNNING__"
        except Exception:
            continue
    return None


def stop_profile(profile_dir):
    needle = f"--user-data-dir={profile_dir}"
    my_pid = os.getpid()
    for pid_str in os.listdir("/proc"):
        if not pid_str.isdigit():
            continue
        pid = int(pid_str)
        if pid == my_pid:
            continue
        try:
            raw = open(f"/proc/{pid}/cmdline", "rb").read()
            cmd = raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore")
            if needle in cmd and any(b in cmd for b in ("chrome", "chromium", "brave")):
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass


def start_slot_process(browser, slot, x, y, w, h, env, login_mode=False):
    slot_type = slot.get("type", "web")
    if slot_type == "app":
        cmd_str = str(slot.get("exec_cmd") or slot.get("url") or "").strip()
        if not cmd_str:
            return
        # Strip freedesktop % placeholders (%u, %U, %f, %F, %i, %c, %k)
        parts = [p for p in shlex.split(cmd_str) if not re.match(r"^%[a-zA-Z]$", p)]
        if parts:
            subprocess.Popen(parts, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return

    profile_dir = os.path.join(WIDGETS_DIR, slot["profile"])
    os.makedirs(profile_dir, exist_ok=True)
    url = slot["url"]
    launch_env = env.copy()
    desktop_hint = widget_desktop_path(slot["id"])
    if os.path.exists(desktop_hint):
        launch_env["BAMF_DESKTOP_FILE_HINT"] = desktop_hint

    if login_mode:
        cmd = [
            browser,
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ]
    else:
        cmd = [
            browser,
            f"--app={url}",
            f"--class={slot['wm_class']}",
            f"--user-data-dir={profile_dir}",
            f"--window-position={x},{y}",
            f"--window-size={w},{h}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
        ]
    subprocess.Popen(cmd, env=launch_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def align_window(slot, x, y, w, h, opacity_pct, env):
    wid = find_wid(slot.get("wm_class", ""), env)
    if not wid:
        return False

    try:
        wm_state = subprocess.check_output(["xprop", "-id", wid, "WM_STATE"], env=env, text=True, timeout=2)
        if "Iconic" in wm_state:
            subprocess.run(["wmctrl", "-i", "-a", wid], env=env, stderr=subprocess.DEVNULL)
            time.sleep(0.15)
    except Exception:
        pass

    op_cardinal = str(int(round((opacity_pct / 100.0) * 4294967295)))
    subprocess.run(
        ["xprop", "-id", wid, "-f", "_MOTIF_WM_HINTS", "32c", "-set", "_MOTIF_WM_HINTS", "2, 0, 0, 0, 0"],
        env=env,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["xprop", "-id", wid, "-f", "_NET_WM_WINDOW_OPACITY", "32c", "-set", "_NET_WM_WINDOW_OPACITY", op_cardinal],
        env=env,
        stderr=subprocess.DEVNULL,
    )
    if slot.get("type", "web") == "web":
        desktop_hint = widget_desktop_path(slot["id"])
        subprocess.run(
            ["xprop", "-id", wid, "-f", "_BAMF_DESKTOP_FILE", "8s", "-set", "_BAMF_DESKTOP_FILE", desktop_hint],
            env=env,
            stderr=subprocess.DEVNULL,
        )
    subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "remove,maximized_vert,maximized_horz"], env=env, stderr=subprocess.DEVNULL)
    subprocess.run(["wmctrl", "-i", "-r", wid, "-t", "-1"], env=env, stderr=subprocess.DEVNULL)
    if shutil.which("xdotool"):
        subprocess.run(
            ["xdotool", "windowmove", wid, str(x), str(y), "windowsize", wid, str(w), str(h)],
            env=env,
            stderr=subprocess.DEVNULL,
        )
    subprocess.run(["wmctrl", "-i", "-r", wid, "-e", f"0,{x},{y},{w},{h}"], env=env, stderr=subprocess.DEVNULL)
    subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "add,below,sticky"], env=env, stderr=subprocess.DEVNULL)
    subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "add,skip_taskbar,skip_pager"], env=env, stderr=subprocess.DEVNULL)
    return True


def align_all(env):
    cfg = load_config()
    screen_w, screen_h = get_screen_size(env)
    for slot in cfg.get("slots", []):
        if not slot.get("enabled", False):
            continue
        x, y, w, h, opacity, _ = resolve_slot_geom(slot, screen_w, screen_h)
        align_window(slot, x, y, w, h, opacity, env)


def cmd_apply(restart_urls=False):
    env = ensure_display_env()
    browser = detect_browser()
    if not browser:
        print("Error: Chromium系ブラウザが見つかりません。", file=sys.stderr)
        sys.exit(1)

    prev_active = None
    if shutil.which("xdotool"):
        try:
            prev_active = subprocess.check_output(["xdotool", "getactivewindow"], env=env, text=True, timeout=2).strip()
        except Exception:
            prev_active = None

    sync_configs(restart_devilspie=True, update_plank=True, env=env)

    # Always stop legacy Gmail (miniweb) profile if still lingering
    stop_profile(os.path.join(WIDGETS_DIR, "miniweb"))

    cfg = load_config()
    slots = cfg.get("slots", [])
    screen_w, screen_h = get_screen_size(env)

    need_launch = []
    for slot in slots:
        slot_type = slot.get("type", "web")
        if slot_type == "web":
            pdir = os.path.join(WIDGETS_DIR, slot["profile"])
            if not slot.get("enabled", False):
                stop_profile(pdir)
                continue
            running_url = get_running_profile_url(pdir)
            if restart_urls and running_url is not None:
                stop_profile(pdir)
                time.sleep(0.4)
                running_url = None
            if running_url is None:
                need_launch.append(slot)
        else:
            wid = find_wid(slot.get("wm_class", ""), env)
            if not slot.get("enabled", False):
                if wid:
                    subprocess.run(["wmctrl", "-i", "-c", wid], env=env, stderr=subprocess.DEVNULL)
                continue
            if not wid:
                need_launch.append(slot)

    for slot in need_launch:
        x, y, w, h, _, _ = resolve_slot_geom(slot, screen_w, screen_h)
        start_slot_process(browser, slot, x, y, w, h, env, login_mode=False)

    if need_launch:
        enabled_slots = [s for s in slots if s.get("enabled", False)]
        done = set()
        for _ in range(20):
            for slot in enabled_slots:
                sid = slot["id"]
                if sid in done:
                    continue
                x, y, w, h, opacity, _ = resolve_slot_geom(slot, screen_w, screen_h)
                if align_window(slot, x, y, w, h, opacity, env):
                    done.add(sid)
            if len(done) == len(enabled_slots):
                break
            time.sleep(0.5)
        time.sleep(0.8)

    align_all(env)

    if prev_active:
        widget_wids = set()
        for slot in slots:
            wid = find_wid(slot.get("wm_class", ""), env)
            if wid:
                widget_wids.add(int(wid, 16))
        try:
            if int(prev_active) not in widget_wids:
                subprocess.run(["wmctrl", "-i", "-a", hex(int(prev_active))], env=env, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def cmd_unlock():
    """Temporarily restore titlebar/resize borders and bring widgets forward for direct mouse positioning."""
    env = ensure_display_env()
    cfg = load_config()
    for slot in cfg.get("slots", []):
        if not slot.get("enabled", False):
            continue
        wid = find_wid(slot.get("wm_class", ""), env)
        if not wid:
            continue
        subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "remove,below"], env=env, stderr=subprocess.DEVNULL)
        subprocess.run(
            ["xprop", "-id", wid, "-f", "_MOTIF_WM_HINTS", "32c", "-set", "_MOTIF_WM_HINTS", "2, 0, 1, 0, 0"],
            env=env,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(["wmctrl", "-i", "-a", wid], env=env, stderr=subprocess.DEVNULL)


def cmd_capture():
    """Capture current desktop coordinates/sizes of running widgets into widgets.json and lock them again."""
    env = ensure_display_env()
    cfg = load_config()
    changed = False
    for slot in cfg.get("slots", []):
        if not slot.get("enabled", False):
            continue
        wid = find_wid(slot.get("wm_class", ""), env)
        if not wid:
            continue
        try:
            out = subprocess.check_output(["xwininfo", "-id", wid], env=env, text=True, timeout=2)
            mx = re.search(r"Absolute upper-left X:\s+(-?\d+)", out)
            my = re.search(r"Absolute upper-left Y:\s+(-?\d+)", out)
            mw = re.search(r"Width:\s+(\d+)", out)
            mh = re.search(r"Height:\s+(\d+)", out)
            if mx and my and mw and mh:
                slot["x"] = max(0, int(mx.group(1)))
                slot["y"] = max(28, int(my.group(1)))
                slot["width"] = max(200, int(mw.group(1)))
                slot["height"] = max(160, int(mh.group(1)))
                slot["align_right"] = False
                changed = True
        except Exception:
            pass
    if changed:
        save_config(cfg)
    cmd_apply(restart_urls=False)


def cmd_focus(slot_id):
    env = ensure_display_env()
    cfg = load_config()
    slot = next((s for s in cfg.get("slots", []) if s["id"] == slot_id), None)
    if not slot:
        return
    wid = find_wid(slot.get("wm_class", ""), env)
    if wid:
        subprocess.run(["wmctrl", "-i", "-a", wid], env=env, stderr=subprocess.DEVNULL)
    else:
        slot["enabled"] = True
        save_config(cfg)
        cmd_apply(restart_urls=False)
        wid = find_wid(slot.get("wm_class", ""), env)
        if wid:
            subprocess.run(["wmctrl", "-i", "-a", wid], env=env, stderr=subprocess.DEVNULL)


def cmd_login(slot_id=None):
    env = ensure_display_env()
    browser = detect_browser()
    if not browser:
        print("Error: Chromium系ブラウザが見つかりません。", file=sys.stderr)
        sys.exit(1)
    cfg = load_config()
    screen_w, screen_h = get_screen_size(env)
    for slot in cfg.get("slots", []):
        if slot.get("type", "web") != "web":
            continue
        if slot_id and slot["id"] != slot_id:
            continue
        if not slot_id and not slot.get("enabled", False):
            continue
        pdir = os.path.join(WIDGETS_DIR, slot["profile"])
        stop_profile(pdir)
        time.sleep(0.5)
        x, y, w, h, _, _ = resolve_slot_geom(slot, screen_w, screen_h)
        start_slot_process(browser, slot, x, y, w, h, env, login_mode=True)


def cmd_stop():
    cfg = load_config()
    for slot in cfg.get("slots", []):
        if slot.get("type", "web") == "web":
            stop_profile(os.path.join(WIDGETS_DIR, slot["profile"]))
    stop_profile(os.path.join(WIDGETS_DIR, "miniweb"))


def cmd_youtube_music():
    env = ensure_display_env()
    wid = find_wid("YouTubeMusicApp", env)
    if wid:
        subprocess.run(["wmctrl", "-i", "-a", wid], env=env, stderr=subprocess.DEVNULL)
        return
    browser = detect_browser()
    if not browser:
        sys.exit(1)
    yt_dir = os.path.join(WIDGETS_DIR, "ytmusic")
    os.makedirs(yt_dir, exist_ok=True)
    launch_env = env.copy()
    yt_desktop = os.path.join(APPS_DIR, "youtube-music.desktop")
    if os.path.exists(yt_desktop):
        launch_env["BAMF_DESKTOP_FILE_HINT"] = yt_desktop
    subprocess.Popen(
        [
            browser,
            "--app=https://music.youtube.com",
            "--class=YouTubeMusicApp",
            f"--user-data-dir={yt_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        env=launch_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main():
    args = sys.argv[1:]
    if not args:
        cmd_apply(restart_urls=False)
    elif args[0] == "sync-configs":
        sync_configs(restart_devilspie=False, update_plank=False)
    elif args[0] == "apply":
        cmd_apply(restart_urls="--restart-urls" in args)
    elif args[0] == "align":
        align_all(ensure_display_env())
    elif args[0] == "unlock":
        cmd_unlock()
    elif args[0] == "capture":
        cmd_capture()
    elif args[0] == "focus" and len(args) >= 2:
        cmd_focus(args[1])
    elif args[0] == "login":
        cmd_login(args[1] if len(args) >= 2 else None)
    elif args[0] == "stop":
        cmd_stop()
    elif args[0] == "youtube-music":
        cmd_youtube_music()
    else:
        print(f"Unknown command: {' '.join(args)}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
