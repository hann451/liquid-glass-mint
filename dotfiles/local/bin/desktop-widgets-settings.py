#!/usr/bin/env python3
"""Visual GTK3 configurator for Desktop Embedded Web & App Widgets."""

import configparser
import glob
import json
import os
import re
import subprocess
import sys
import threading
import uuid

import cairo
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".config", "desktop-widgets", "widgets.json")
MANAGER_BIN = os.path.join(HOME, ".local", "bin", "desktop-widgets-manager.py")

POPULAR_WEB_PRESETS = [
    ("Notion", "https://www.notion.so/"),
    ("TimeTree", "https://timetreeapp.com/calendars"),
    ("Googleカレンダー", "https://calendar.google.com/"),
    ("YouTube Music", "https://music.youtube.com/"),
    ("YouTube", "https://www.youtube.com/"),
    ("ChatGPT", "https://chatgpt.com/"),
    ("Gemini", "https://gemini.google.com/"),
    ("Claude", "https://claude.ai/"),
    ("Spotify", "https://open.spotify.com/"),
    ("Discord", "https://discord.com/app"),
    ("GitHub", "https://github.com/"),
    ("Todoist", "https://app.todoist.com/"),
    ("Google Keep", "https://keep.google.com/"),
    ("X (Twitter)", "https://x.com/"),
]


def detect_screen_size():
    try:
        out = subprocess.check_output(["xrandr", "--current"], text=True, timeout=2)
        m = re.search(r"connected primary (\d+)x(\d+)\+", out)
        if m:
            return int(m.group(1)), int(m.group(2))
        m2 = re.search(r"\b(\d+)x(\d+)\s+\d+\.\d+\*", out)
        if m2:
            return int(m2.group(1)), int(m2.group(2))
    except Exception:
        pass
    return 1920, 1080


def scan_installed_apps():
    apps = []
    seen = set()
    search_dirs = [
        os.path.join(HOME, ".local", "share", "applications"),
        "/usr/share/applications",
        "/var/lib/flatpak/exports/share/applications",
    ]
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for path in sorted(glob.glob(os.path.join(d, "*.desktop"))):
            base = os.path.basename(path)
            if base.startswith("desktop-widget-") or base in seen:
                continue
            cp = configparser.ConfigParser(interpolation=None)
            try:
                cp.read(path, encoding="utf-8")
                if "Desktop Entry" not in cp:
                    continue
                ent = cp["Desktop Entry"]
                if ent.get("NoDisplay", "").lower() == "true" or ent.get("Hidden", "").lower() == "true":
                    continue
                if ent.get("Type", "Application") != "Application":
                    continue
                name = ent.get("Name[ja]") or ent.get("Name") or ""
                exec_cmd = ent.get("Exec", "").strip()
                if not name or not exec_cmd:
                    continue
                wm_class = ent.get("StartupWMClass", "").strip() or os.path.splitext(base)[0]
                seen.add(base)
                apps.append({
                    "name": name,
                    "exec_cmd": exec_cmd,
                    "wm_class": wm_class,
                    "desktop_file": path,
                })
            except Exception:
                continue
    apps.sort(key=lambda a: a["name"].lower())
    return apps


class AddWidgetDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="ウィジェット / アプリを追加", transient_for=parent, flags=0)
        self.set_default_size(540, 440)
        self.add_button("キャンセル", Gtk.ResponseType.CANCEL)
        self.selected_payload = None

        box = self.get_content_area()
        box.set_border_width(10)
        box.set_spacing(8)

        nb = Gtk.Notebook()
        box.pack_start(nb, True, True, 0)

        # Tab 1: Popular Web Services
        tab1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tab1.set_border_width(12)
        tab1.pack_start(Gtk.Label(label="追加したいWebサービスをクリックしてください：", xalign=0), False, False, 0)
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(3)
        flow.set_row_spacing(8)
        flow.set_column_spacing(8)
        for name, url in POPULAR_WEB_PRESETS:
            btn = Gtk.Button(label=name)
            btn.connect("clicked", self._pick_web, name, url)
            flow.add(btn)
        sw1 = Gtk.ScrolledWindow()
        sw1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw1.add(flow)
        tab1.pack_start(sw1, True, True, 0)
        nb.append_page(tab1, Gtk.Label(label="人気Webサービス"))

        # Tab 2: Custom URL
        tab2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tab2.set_border_width(14)
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        ent_name = Gtk.Entry(placeholder_text="例: 会社のポータル")
        ent_url = Gtk.Entry(placeholder_text="https://...")
        ent_name.set_hexpand(True)
        ent_url.set_hexpand(True)
        grid.attach(Gtk.Label(label="名前:", xalign=0), 0, 0, 1, 1)
        grid.attach(ent_name, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="URL:", xalign=0), 0, 1, 1, 1)
        grid.attach(ent_url, 1, 1, 1, 1)
        tab2.pack_start(grid, False, False, 0)
        btn_add_url = Gtk.Button(label="このURLを追加")
        btn_add_url.get_style_context().add_class("suggested-action")
        btn_add_url.connect("clicked", lambda _b: self._pick_custom_url(ent_name.get_text(), ent_url.get_text()))
        tab2.pack_start(btn_add_url, False, False, 6)
        nb.append_page(tab2, Gtk.Label(label="好きなURL"))

        # Tab 3: Installed PC Apps
        tab3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tab3.set_border_width(10)
        search = Gtk.SearchEntry(placeholder_text="アプリ名で検索...")
        tab3.pack_start(search, False, False, 0)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        apps = scan_installed_apps()
        for app in apps:
            row = Gtk.ListBoxRow()
            row.app_data = app
            lbl = Gtk.Label(label=f"{app['name']}   ({app['wm_class']})", xalign=0)
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            lbl.set_margin_top(4)
            lbl.set_margin_bottom(4)
            row.add(lbl)
            listbox.add(row)

        def filter_func(row):
            q = search.get_text().strip().lower()
            if not q:
                return True
            ad = row.app_data
            return q in ad["name"].lower() or q in ad["wm_class"].lower()

        listbox.set_filter_func(filter_func)
        search.connect("search-changed", lambda _s: listbox.invalidate_filter())

        sw3 = Gtk.ScrolledWindow()
        sw3.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw3.add(listbox)
        tab3.pack_start(sw3, True, True, 0)

        btn_add_app = Gtk.Button(label="選択したアプリを追加")
        btn_add_app.get_style_context().add_class("suggested-action")

        def on_pick_app(_b):
            row = listbox.get_selected_row()
            if row:
                self._pick_app(row.app_data)

        btn_add_app.connect("clicked", on_pick_app)
        listbox.connect("row-activated", lambda _lb, row: self._pick_app(row.app_data))
        tab3.pack_start(btn_add_app, False, False, 0)
        nb.append_page(tab3, Gtk.Label(label="PC内アプリ"))

        self.show_all()

    def _pick_web(self, _btn, name, url):
        self.selected_payload = {"type": "web", "name": name, "url": url}
        self.response(Gtk.ResponseType.OK)

    def _pick_custom_url(self, name, url):
        url = url.strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.selected_payload = {"type": "web", "name": name.strip() or "Webウィジェット", "url": url}
        self.response(Gtk.ResponseType.OK)

    def _pick_app(self, app_data):
        self.selected_payload = {
            "type": "app",
            "name": app_data["name"],
            "exec_cmd": app_data["exec_cmd"],
            "wm_class": app_data["wm_class"],
            "desktop_file": app_data["desktop_file"],
        }
        self.response(Gtk.ResponseType.OK)


class DesktopCanvas(Gtk.DrawingArea):
    def __init__(self, settings_win):
        super().__init__()
        self.win = settings_win
        self.set_size_request(440, 220)
        self.drag_mode = None  # "move" or "resize"
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.orig_x = 0
        self.orig_y = 0
        self.orig_w = 0
        self.orig_h = 0

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("button-release-event", self.on_release)

    def _layout_metrics(self):
        alloc = self.get_allocation()
        sw, sh = self.win.screen_w, self.win.screen_h
        scale = min((alloc.width - 16) / sw, (alloc.height - 12) / sh)
        scale = max(0.05, scale)
        ox = (alloc.width - sw * scale) / 2.0
        oy = (alloc.height - sh * scale) / 2.0
        return ox, oy, scale

    def _slot_rect_screen(self, slot):
        sw, sh = self.win.screen_w, self.win.screen_h
        w = int(slot.get("width", 480))
        h = int(slot.get("height", 400))
        if slot.get("align_right", True):
            x = max(0, sw - w - int(slot.get("right_margin", 32)))
        else:
            x = int(slot.get("x", 360))
        y = int(slot.get("y", 52))
        return x, y, w, h

    def _round_rect(self, cr, x, y, w, h, r):
        rad = min(r, w / 2.0, h / 2.0)
        cr.new_sub_path()
        cr.arc(x + w - rad, y + rad, rad, -1.5708, 0)
        cr.arc(x + w - rad, y + h - rad, rad, 0, 1.5708)
        cr.arc(x + rad, y + h - rad, rad, 1.5708, 3.14159)
        cr.arc(x + rad, y + rad, rad, 3.14159, 4.71239)
        cr.close_path()

    def on_draw(self, _widget, cr):
        ox, oy, sc = self._layout_metrics()
        sw, sh = self.win.screen_w, self.win.screen_h
        dw, dh = sw * sc, sh * sc

        # Desktop background preview
        self._round_rect(cr, ox, oy, dw, dh, 8)
        pat = cairo.LinearGradient(ox, oy, ox + dw, oy + dh)
        pat.add_color_stop_rgb(0.0, 0.06, 0.10, 0.28)
        pat.add_color_stop_rgb(0.55, 0.12, 0.24, 0.50)
        pat.add_color_stop_rgb(1.0, 0.08, 0.13, 0.34)
        cr.set_source(pat)
        cr.fill_preserve(cr)
        cr.set_source_rgba(1, 1, 1, 0.28)
        cr.set_line_width(1.2)
        cr.stroke()

        # Top panel & bottom dock guide
        cr.rectangle(ox, oy, dw, 28 * sc)
        cr.set_source_rgba(0.1, 0.12, 0.18, 0.65)
        cr.fill()

        dock_w = min(dw * 0.48, 620 * sc)
        dock_h = 46 * sc
        self._round_rect(cr, ox + (dw - dock_w) / 2, oy + dh - dock_h - 6 * sc, dock_w, dock_h, 6)
        cr.set_source_rgba(0.85, 0.90, 0.98, 0.35)
        cr.fill()

        # Left Conky guides
        for cy, ch in ((56, 218), (300, 256), (578, 210)):
            self._round_rect(cr, ox + 36 * sc, oy + cy * sc, 296 * sc, ch * sc, 5)
            cr.set_source_rgba(0.25, 0.35, 0.55, 0.42)
            cr.fill_preserve()
            cr.set_source_rgba(1, 1, 1, 0.22)
            cr.set_line_width(0.8)
            cr.stroke()

        # Draw widget slots
        for idx, slot in enumerate(self.win.config.get("slots", [])):
            if not slot.get("enabled", False):
                continue
            sx, sy, sw_s, sh_s = self._slot_rect_screen(slot)
            cx = ox + sx * sc
            cy = oy + sy * sc
            cw = sw_s * sc
            ch = sh_s * sc
            is_sel = idx == self.win.selected_idx

            self._round_rect(cr, cx, cy, cw, ch, 6)
            if is_sel:
                cr.set_source_rgba(0.30, 0.68, 1.0, 0.42)
            else:
                cr.set_source_rgba(0.14, 0.18, 0.28, 0.72)
            cr.fill_preserve()
            cr.set_source_rgba(0.55, 0.85, 1.0, 0.95) if is_sel else cr.set_source_rgba(1, 1, 1, 0.45)
            cr.set_line_width(2.0 if is_sel else 1.0)
            cr.stroke()

            cr.select_font_face(cr, "Noto Sans CJK JP", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(11.5)
            cr.set_source_rgba(1, 1, 1, 0.96)
            cr.move_to(cx + 8, cy + 17)
            cr.show_text(slot.get("name", slot["id"]))

            cr.select_font_face(cr, "Noto Sans CJK JP", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9.5)
            cr.set_source_rgba(0.86, 0.92, 1.0, 0.85)
            cr.move_to(cx + 8, cy + 31)
            cr.show_text(f"{sw_s}×{sh_s}")

            # Bottom-right resize handle
            if is_sel:
                cr.rectangle(cx + cw - 10, cy + ch - 10, 10, 10)
                cr.set_source_rgba(0.65, 0.90, 1.0, 0.95)
                cr.fill()

    def on_press(self, _w, event):
        ox, oy, sc = self._layout_metrics()
        slots = self.win.config.get("slots", [])
        hit_idx = None
        hit_mode = None

        for idx in range(len(slots) - 1, -1, -1):
            slot = slots[idx]
            if not slot.get("enabled", False):
                continue
            sx, sy, sw_s, sh_s = self._slot_rect_screen(slot)
            cx, cy, cw, ch = ox + sx * sc, oy + sy * sc, sw_s * sc, sh_s * sc
            if cx <= event.x <= cx + cw and cy <= event.y <= cy + ch:
                hit_idx = idx
                if event.x >= cx + cw - 14 and event.y >= cy + ch - 14:
                    hit_mode = "resize"
                else:
                    hit_mode = "move"
                break

        if hit_idx is not None:
            self.win.select_slot(hit_idx)
            slot = slots[hit_idx]
            sx, sy, sw_s, sh_s = self._slot_rect_screen(slot)
            self.drag_mode = hit_mode
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.orig_x = sx
            self.orig_y = sy
            self.orig_w = sw_s
            self.orig_h = sh_s

    def on_motion(self, _w, event):
        if not self.drag_mode:
            return
        _, _, sc = self._layout_metrics()
        dx = int(round((event.x - self.drag_start_x) / sc / 5.0) * 5)
        dy = int(round((event.y - self.drag_start_y) / sc / 5.0) * 5)
        slot = self.win.config["slots"][self.win.selected_idx]

        if self.drag_mode == "move":
            slot["align_right"] = False
            slot["x"] = max(0, min(self.win.screen_w - int(slot["width"]), self.orig_x + dx))
            slot["y"] = max(28, min(self.win.screen_h - int(slot["height"]), self.orig_y + dy))
        elif self.drag_mode == "resize":
            slot["width"] = max(220, min(self.win.screen_w - 40, self.orig_w + dx))
            slot["height"] = max(160, min(self.win.screen_h - 60, self.orig_h + dy))

        self.win.refresh_right_pane_from_slot()
        self.queue_draw()

    def on_release(self, _w, _event):
        self.drag_mode = None


class WidgetSettingsWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="デスクトップウィジェット設定")
        self.set_default_size(880, 700)
        self.set_border_width(12)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.screen_w, self.screen_h = detect_screen_size()
        self.config = self.load_config()
        self.selected_idx = 0
        self._syncing_ui = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(root)

        header = Gtk.Label()
        header.set_markup(
            "<b>デスクトップウィジェット直感レイアウト設定</b>  "
            "<span size='small'>下のミニ画面でドラッグ移動・右下角でサイズ変更、または実画面を直接動かして固定できます。</span>"
        )
        header.set_xalign(0)
        root.pack_start(header, False, False, 0)

        # Visual desktop layout canvas
        self.canvas = DesktopCanvas(self)
        root.pack_start(self.canvas, False, False, 0)

        direct_bar = Gtk.Box(spacing=8)
        btn_unlock = Gtk.Button(label="🖱 実画面で直接ドラッグ＆リサイズする")
        btn_unlock.connect("clicked", lambda _b: self.run_manager_async(["unlock"], "実画面の枠を表示しました。マウスで移動・リサイズ後に右の「固定して保存」を押してください。"))
        btn_capture = Gtk.Button(label="📌 実画面の今の位置・サイズで固定して保存")
        btn_capture.connect("clicked", self._on_capture_clicked)
        direct_bar.pack_start(btn_unlock, True, True, 0)
        direct_bar.pack_start(btn_capture, True, True, 0)
        root.pack_start(direct_bar, False, False, 0)

        # Bottom split: left slot list + right detail editor
        paned = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.pack_start(paned, True, True, 0)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left_box.set_size_request(250, -1)
        paned.pack_start(left_box, False, False, 0)

        self.slot_listbox = Gtk.ListBox()
        self.slot_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.slot_listbox.connect("row-selected", self._on_row_selected)
        sw_list = Gtk.ScrolledWindow()
        sw_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw_list.add(self.slot_listbox)
        left_box.pack_start(sw_list, True, True, 0)

        list_btns = Gtk.Box(spacing=6)
        btn_add = Gtk.Button(label="＋ アプリ / Webを追加")
        btn_add.connect("clicked", self._on_add_clicked)
        btn_del = Gtk.Button(label="削除")
        btn_del.connect("clicked", self._on_delete_clicked)
        list_btns.pack_start(btn_add, True, True, 0)
        list_btns.pack_start(btn_del, False, False, 0)
        left_box.pack_start(list_btns, False, False, 0)

        # Right detail editor
        right_frame = Gtk.Frame(label=" 選択中のウィジェット設定 ")
        paned.pack_start(right_frame, True, True, 0)
        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        grid.set_border_width(12)
        right_frame.add(grid)

        r = 0
        self.sw_enabled = Gtk.Switch(halign=Gtk.Align.START)
        self.sw_dock = Gtk.Switch(halign=Gtk.Align.START)
        sw_row = Gtk.Box(spacing=16)
        sw_row.pack_start(self.sw_enabled, False, False, 0)
        sw_row.pack_start(Gtk.Label(label="ドックにも固定:"), False, False, 0)
        sw_row.pack_start(self.sw_dock, False, False, 0)
        grid.attach(Gtk.Label(label="表示する:", xalign=0), 0, r, 1, 1)
        grid.attach(sw_row, 1, r, 2, 1)

        r += 1
        self.ent_name = Gtk.Entry(hexpand=True)
        grid.attach(Gtk.Label(label="名前:", xalign=0), 0, r, 1, 1)
        grid.attach(self.ent_name, 1, r, 2, 1)

        r += 1
        self.lbl_url_or_cmd = Gtk.Label(label="URL:", xalign=0)
        self.ent_url = Gtk.Entry(hexpand=True)
        grid.attach(self.lbl_url_or_cmd, 0, r, 1, 1)
        grid.attach(self.ent_url, 1, r, 2, 1)

        r += 1
        self.sp_w = Gtk.SpinButton.new_with_range(200, 1800, 10)
        self.sp_h = Gtk.SpinButton.new_with_range(160, 1040, 10)
        sz_box = Gtk.Box(spacing=8)
        sz_box.pack_start(Gtk.Label(label="幅:"), False, False, 0)
        sz_box.pack_start(self.sp_w, False, False, 0)
        sz_box.pack_start(Gtk.Label(label=" 高さ:"), False, False, 0)
        sz_box.pack_start(self.sp_h, False, False, 0)
        grid.attach(Gtk.Label(label="サイズ(px):", xalign=0), 0, r, 1, 1)
        grid.attach(sz_box, 1, r, 2, 1)

        r += 1
        self.chk_right = Gtk.CheckButton(label="画面右端に自動吸着")
        self.sp_margin = Gtk.SpinButton.new_with_range(0, 500, 4)
        self.sp_x = Gtk.SpinButton.new_with_range(0, 3840, 10)
        self.sp_y = Gtk.SpinButton.new_with_range(28, 2160, 10)
        pos_v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        pos_v.pack_start(self.chk_right, False, False, 0)
        cbox = Gtk.Box(spacing=6)
        cbox.pack_start(Gtk.Label(label="右余白:"), False, False, 0)
        cbox.pack_start(self.sp_margin, False, False, 0)
        cbox.pack_start(Gtk.Label(label=" X:"), False, False, 0)
        cbox.pack_start(self.sp_x, False, False, 0)
        cbox.pack_start(Gtk.Label(label=" Y:"), False, False, 0)
        cbox.pack_start(self.sp_y, False, False, 0)
        pos_v.pack_start(cbox, False, False, 0)
        grid.attach(Gtk.Label(label="配置:", xalign=0), 0, r, 1, 1)
        grid.attach(pos_v, 1, r, 2, 1)

        r += 1
        self.sc_opacity = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 50, 100, 1)
        self.sc_opacity.set_value_pos(Gtk.PositionType.RIGHT)
        self.sc_opacity.set_hexpand(True)
        grid.attach(Gtk.Label(label="透過度(%):", xalign=0), 0, r, 1, 1)
        grid.attach(self.sc_opacity, 1, r, 2, 1)

        r += 1
        self.sp_corner = Gtk.SpinButton.new_with_range(0, 25, 1)
        self.sp_corner.set_halign(Gtk.Align.START)
        self.btn_login = Gtk.Button(label="通常ブラウザでログイン / 拡張設定")
        self.btn_login.connect("clicked", self._on_login_clicked)
        row_end = Gtk.Box(spacing=12)
        row_end.pack_start(self.sp_corner, False, False, 0)
        row_end.pack_end(self.btn_login, False, False, 0)
        grid.attach(Gtk.Label(label="角丸(px):", xalign=0), 0, r, 1, 1)
        grid.attach(row_end, 1, r, 2, 1)

        # Wire live updates from controls -> slot & canvas
        self.sw_enabled.connect("notify::active", self._on_detail_changed)
        self.sw_dock.connect("notify::active", self._on_detail_changed)
        self.ent_name.connect("changed", self._on_detail_changed)
        self.ent_url.connect("changed", self._on_detail_changed)
        self.sp_w.connect("value-changed", self._on_detail_changed)
        self.sp_h.connect("value-changed", self._on_detail_changed)
        self.chk_right.connect("toggled", self._on_detail_changed)
        self.sp_margin.connect("value-changed", self._on_detail_changed)
        self.sp_x.connect("value-changed", self._on_detail_changed)
        self.sp_y.connect("value-changed", self._on_detail_changed)
        self.sc_opacity.connect("value-changed", self._on_detail_changed)
        self.sp_corner.connect("value-changed", self._on_detail_changed)

        footer = Gtk.Box(spacing=8)
        root.pack_start(footer, False, False, 0)
        self.status_label = Gtk.Label(label="", xalign=0)
        footer.pack_start(self.status_label, True, True, 0)

        self.btn_restart = Gtk.Button(label="URL変更を反映（再起動）")
        self.btn_restart.connect("clicked", lambda _b: self.save_and_apply(restart_urls=True))
        footer.pack_end(self.btn_restart, False, False, 0)

        self.btn_apply = Gtk.Button(label="保存して今すぐ反映")
        self.btn_apply.get_style_context().add_class("suggested-action")
        self.btn_apply.connect("clicked", lambda _b: self.save_and_apply(restart_urls=False))
        footer.pack_end(self.btn_apply, False, False, 0)

        self.rebuild_list(select_idx=0)

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"slots": []}

    def save_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def rebuild_list(self, select_idx=0):
        for child in self.slot_listbox.get_children():
            self.slot_listbox.remove(child)
        slots = self.config.get("slots", [])
        for idx, slot in enumerate(slots):
            row = Gtk.ListBoxRow()
            row.slot_idx = idx
            on_mark = "●" if slot.get("enabled", False) else "○"
            t_mark = "アプリ" if slot.get("type", "web") == "app" else "Web"
            lbl = Gtk.Label(label=f"{on_mark} {slot.get('name', slot['id'])}  [{t_mark}]", xalign=0)
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            lbl.set_margin_top(6)
            lbl.set_margin_bottom(6)
            row.add(lbl)
            self.slot_listbox.add(row)
        self.slot_listbox.show_all()
        if slots:
            idx = max(0, min(select_idx, len(slots) - 1))
            self.select_slot(idx)
        else:
            self.selected_idx = -1
            self.canvas.queue_draw()

    def select_slot(self, idx):
        slots = self.config.get("slots", [])
        if not (0 <= idx < len(slots)):
            return
        self.selected_idx = idx
        row = self.slot_listbox.get_row_at_index(idx)
        if row and self.slot_listbox.get_selected_row() != row:
            self.slot_listbox.select_row(row)
        self.refresh_right_pane_from_slot()
        self.canvas.queue_draw()

    def _on_row_selected(self, _lb, row):
        if row is not None:
            self.selected_idx = row.slot_idx
            self.refresh_right_pane_from_slot()
            self.canvas.queue_draw()

    def refresh_right_pane_from_slot(self):
        slots = self.config.get("slots", [])
        if not (0 <= self.selected_idx < len(slots)):
            return
        self._syncing_ui = True
        s = slots[self.selected_idx]
        is_web = s.get("type", "web") == "web"
        self.sw_enabled.set_active(bool(s.get("enabled", True)))
        self.sw_dock.set_active(bool(s.get("pin_to_dock", False)))
        self.ent_name.set_text(s.get("name", ""))
        self.lbl_url_or_cmd.set_text("URL:" if is_web else "起動コマンド:")
        self.ent_url.set_text(s.get("url", "") if is_web else s.get("exec_cmd", ""))
        self.sp_w.set_value(int(s.get("width", 480)))
        self.sp_h.set_value(int(s.get("height", 400)))
        ar = bool(s.get("align_right", True))
        self.chk_right.set_active(ar)
        self.sp_margin.set_value(int(s.get("right_margin", 32)))
        self.sp_x.set_value(int(s.get("x", 360)))
        self.sp_y.set_value(int(s.get("y", 52)))
        self.sp_margin.set_sensitive(ar)
        self.sp_x.set_sensitive(not ar)
        self.sc_opacity.set_value(int(s.get("opacity", 88)))
        self.sp_corner.set_value(int(s.get("corner_radius", 20)))
        self.btn_login.set_visible(is_web)
        self._syncing_ui = False

    def _on_detail_changed(self, *_args):
        if self._syncing_ui:
            return
        slots = self.config.get("slots", [])
        if not (0 <= self.selected_idx < len(slots)):
            return
        s = slots[self.selected_idx]
        is_web = s.get("type", "web") == "web"
        s["enabled"] = self.sw_enabled.get_active()
        s["pin_to_dock"] = self.sw_dock.get_active()
        s["name"] = self.ent_name.get_text().strip() or s["id"]
        if is_web:
            s["url"] = self.ent_url.get_text().strip() or s.get("url", "")
        else:
            s["exec_cmd"] = self.ent_url.get_text().strip() or s.get("exec_cmd", "")
        s["width"] = int(self.sp_w.get_value())
        s["height"] = int(self.sp_h.get_value())
        ar = self.chk_right.get_active()
        s["align_right"] = ar
        s["right_margin"] = int(self.sp_margin.get_value())
        s["x"] = int(self.sp_x.get_value())
        s["y"] = int(self.sp_y.get_value())
        self.sp_margin.set_sensitive(ar)
        self.sp_x.set_sensitive(not ar)
        s["opacity"] = int(self.sc_opacity.get_value())
        s["corner_radius"] = int(self.sp_corner.get_value())

        row = self.slot_listbox.get_row_at_index(self.selected_idx)
        if row:
            lbl = row.get_child()
            on_mark = "●" if s["enabled"] else "○"
            t_mark = "アプリ" if not is_web else "Web"
            lbl.set_text(f"{on_mark} {s['name']}  [{t_mark}]")
        self.canvas.queue_draw()

    def _on_add_clicked(self, _btn):
        dlg = AddWidgetDialog(self)
        resp = dlg.run()
        payload = dlg.selected_payload
        dlg.destroy()
        if resp != Gtk.ResponseType.OK or not payload:
            return

        uid = uuid.uuid4().hex[:6]
        slots = self.config.setdefault("slots", [])
        offset = (len(slots) % 5) * 40
        if payload["type"] == "web":
            new_slot = {
                "id": f"web_{uid}",
                "name": payload["name"],
                "type": "web",
                "wm_class": f"DesktopWeb_{uid}",
                "profile": f"prof_{uid}",
                "enabled": True,
                "url": payload["url"],
                "align_right": False,
                "right_margin": 32,
                "x": min(self.screen_w - 480, 380 + offset),
                "y": min(self.screen_h - 420, 60 + offset),
                "width": 460,
                "height": 420,
                "opacity": 88,
                "corner_radius": 20,
                "pin_to_dock": False,
            }
        else:
            new_slot = {
                "id": f"app_{uid}",
                "name": payload["name"],
                "type": "app",
                "wm_class": payload["wm_class"],
                "desktop_file": payload["desktop_file"],
                "exec_cmd": payload["exec_cmd"],
                "profile": "",
                "enabled": True,
                "url": "",
                "align_right": False,
                "right_margin": 32,
                "x": min(self.screen_w - 500, 380 + offset),
                "y": min(self.screen_h - 460, 60 + offset),
                "width": 480,
                "height": 440,
                "opacity": 92,
                "corner_radius": 18,
                "pin_to_dock": False,
            }
        slots.append(new_slot)
        self.rebuild_list(select_idx=len(slots) - 1)
        self.status_label.set_text(f"「{new_slot['name']}」を追加しました。「保存して今すぐ反映」で画面に表示されます。")

    def _on_delete_clicked(self, _btn):
        slots = self.config.get("slots", [])
        if not (0 <= self.selected_idx < len(slots)):
            return
        removed = slots.pop(self.selected_idx)
        self.rebuild_list(select_idx=max(0, self.selected_idx - 1))
        self.status_label.set_text(f"「{removed.get('name')}」を削除しました。「保存して今すぐ反映」で確定します。")

    def _on_login_clicked(self, _btn):
        slots = self.config.get("slots", [])
        if not (0 <= self.selected_idx < len(slots)):
            return
        sid = slots[self.selected_idx]["id"]
        self.status_label.set_text("通常ブラウザでログイン画面を開いています...")
        subprocess.Popen(["python3", MANAGER_BIN, "login", sid])

    def _on_capture_clicked(self, _btn):
        def done_cb():
            self.config = self.load_config()
            self.rebuild_list(select_idx=self.selected_idx)
            self.status_label.set_text("実画面の今の位置とサイズを保存して固定しました！")

        self.run_manager_async(["capture"], "実画面の位置とサイズを取り込んで固定中...", on_success=done_cb)

    def run_manager_async(self, args, working_msg, on_success=None):
        self.btn_apply.set_sensitive(False)
        self.btn_restart.set_sensitive(False)
        self.status_label.set_text(working_msg)

        def worker():
            res = subprocess.run(["python3", MANAGER_BIN] + args, capture_output=True, text=True)
            def finish():
                self.btn_apply.set_sensitive(True)
                self.btn_restart.set_sensitive(True)
                if res.returncode == 0:
                    if on_success:
                        on_success()
                    else:
                        self.status_label.set_text(working_msg if args[0] == "unlock" else "反映しました！")
                else:
                    self.status_label.set_text(f"エラー: {res.stderr.strip() or '実行に失敗しました'}")
                return False
            GLib.idle_add(finish)

        threading.Thread(target=worker, daemon=True).start()

    def save_and_apply(self, restart_urls=False):
        self.save_config()
        args = ["apply", "--restart-urls"] if restart_urls else ["apply"]
        self.run_manager_async(args, "デスクトップへ反映中...")


def main():
    check_only = "--check" in sys.argv[1:]
    win = WidgetSettingsWindow()
    if check_only:
        dlg = AddWidgetDialog(win)
        dlg.destroy()
        win.destroy()
        print("GTK_SETTINGS_CHECK_OK")
        return
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
