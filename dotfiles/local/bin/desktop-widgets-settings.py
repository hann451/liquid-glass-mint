#!/usr/bin/env python3
"""GTK3 GUI settings tool for Desktop Embedded Web Widgets."""

import json
import os
import subprocess
import sys
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

HOME = os.path.expanduser("~")
CONFIG_PATH = os.path.join(HOME, ".config", "desktop-widgets", "widgets.json")
MANAGER_BIN = os.path.join(HOME, ".local", "bin", "desktop-widgets-manager.py")

PRESETS = [
    ("Notion", "https://www.notion.so/"),
    ("TimeTree", "https://timetreeapp.com/calendars"),
    ("Googleカレンダー", "https://calendar.google.com/"),
    ("YouTube Music", "https://music.youtube.com/"),
    ("ChatGPT", "https://chatgpt.com/"),
    ("Gemini", "https://gemini.google.com/"),
]


class WidgetSettingsWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="デスクトップウィジェット設定")
        self.set_default_size(680, 620)
        self.set_border_width(14)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.config = self.load_config()
        self.slot_controls = []

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(root)

        intro = Gtk.Label()
        intro.set_markup(
            "<b>デスクトップ埋め込みWebウィジェット設定</b>\n"
            "<span size='small'>壁紙に常駐させるアプリ（Notion・TimeTree・カレンダー等）のURL・サイズ・位置・透過度を自由に調整できます。</span>"
        )
        intro.set_xalign(0)
        intro.set_line_wrap(True)
        root.pack_start(intro, False, False, 0)

        self.notebook = Gtk.Notebook()
        root.pack_start(self.notebook, True, True, 0)

        for idx, slot in enumerate(self.config.get("slots", [])):
            tab_label = Gtk.Label(label=f"枠{idx + 1}: {slot.get('name', slot['id'])}")
            page = self.build_slot_page(slot, tab_label)
            self.notebook.append_page(page, tab_label)

        note = Gtk.Label()
        note.set_markup(
            "<span size='small' alpha='75%'>"
            "※ 枠1/枠2などの「サイズ・位置・ON/OFF・透過度」はすぐ反映されます。"
            "「角丸(px)」の変更は次回ログイン時（またはパネル設定のCinnamon再起動時）に反映されます。"
            "</span>"
        )
        note.set_xalign(0)
        note.set_line_wrap(True)
        root.pack_start(note, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.pack_start(footer, False, False, 0)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)
        footer.pack_start(self.status_label, True, True, 0)

        self.btn_restart = Gtk.Button(label="URL変更を反映（再起動）")
        self.btn_restart.connect("clicked", lambda _b: self.save_and_apply(restart_urls=True))
        footer.pack_end(self.btn_restart, False, False, 0)

        self.btn_apply = Gtk.Button(label="保存して今すぐ反映")
        self.btn_apply.get_style_context().add_class("suggested-action")
        self.btn_apply.connect("clicked", lambda _b: self.save_and_apply(restart_urls=False))
        footer.pack_end(self.btn_apply, False, False, 0)

    def load_config(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def build_slot_page(self, slot, tab_label):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_border_width(14)

        grid = Gtk.Grid(column_spacing=14, row_spacing=10)
        vbox.pack_start(grid, False, False, 0)

        row = 0
        lbl_en = Gtk.Label(label="表示する（有効）:", xalign=0)
        sw_en = Gtk.Switch()
        sw_en.set_active(bool(slot.get("enabled", True)))
        sw_en.set_halign(Gtk.Align.START)
        grid.attach(lbl_en, 0, row, 1, 1)
        grid.attach(sw_en, 1, row, 1, 1)

        row += 1
        lbl_name = Gtk.Label(label="名前:", xalign=0)
        ent_name = Gtk.Entry()
        ent_name.set_text(slot.get("name", ""))
        ent_name.set_hexpand(True)
        ent_name.connect("changed", lambda e: tab_label.set_text(f"{slot['id'].replace('slot', '枠')}: {e.get_text() or slot['id']}"))
        grid.attach(lbl_name, 0, row, 1, 1)
        grid.attach(ent_name, 1, row, 2, 1)

        row += 1
        lbl_url = Gtk.Label(label="表示URL:", xalign=0)
        ent_url = Gtk.Entry()
        ent_url.set_text(slot.get("url", ""))
        ent_url.set_hexpand(True)
        grid.attach(lbl_url, 0, row, 1, 1)
        grid.attach(ent_url, 1, row, 2, 1)

        row += 1
        lbl_pre = Gtk.Label(label="プリセット:", xalign=0)
        preset_box = Gtk.FlowBox()
        preset_box.set_selection_mode(Gtk.SelectionMode.NONE)
        preset_box.set_max_children_per_line(4)
        for p_name, p_url in PRESETS:
            b = Gtk.Button(label=p_name)
            b.connect("clicked", self._on_preset_clicked, ent_name, ent_url, p_name, p_url)
            preset_box.add(b)
        grid.attach(lbl_pre, 0, row, 1, 1)
        grid.attach(preset_box, 1, row, 2, 1)

        row += 1
        lbl_size = Gtk.Label(label="サイズ（幅 × 高さ px）:", xalign=0)
        size_box = Gtk.Box(spacing=8)
        sp_w = Gtk.SpinButton.new_with_range(240, 1400, 10)
        sp_w.set_value(int(slot.get("width", 540)))
        sp_h = Gtk.SpinButton.new_with_range(180, 1000, 10)
        sp_h.set_value(int(slot.get("height", 420)))
        size_box.pack_start(Gtk.Label(label="幅:"), False, False, 0)
        size_box.pack_start(sp_w, False, False, 0)
        size_box.pack_start(Gtk.Label(label="  高さ:"), False, False, 0)
        size_box.pack_start(sp_h, False, False, 0)
        grid.attach(lbl_size, 0, row, 1, 1)
        grid.attach(size_box, 1, row, 2, 1)

        row += 1
        lbl_pos = Gtk.Label(label="配置:", xalign=0)
        pos_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        chk_right = Gtk.CheckButton(label="画面右端に自動で揃える")
        chk_right.set_active(bool(slot.get("align_right", True)))
        pos_box.pack_start(chk_right, False, False, 0)

        coord_box = Gtk.Box(spacing=8)
        sp_margin = Gtk.SpinButton.new_with_range(0, 400, 4)
        sp_margin.set_value(int(slot.get("right_margin", 32)))
        sp_x = Gtk.SpinButton.new_with_range(0, 3840, 10)
        sp_x.set_value(int(slot.get("x", 1348)))
        sp_y = Gtk.SpinButton.new_with_range(28, 2160, 10)
        sp_y.set_value(int(slot.get("y", 52)))

        coord_box.pack_start(Gtk.Label(label="右余白:"), False, False, 0)
        coord_box.pack_start(sp_margin, False, False, 0)
        coord_box.pack_start(Gtk.Label(label="  X座標:"), False, False, 0)
        coord_box.pack_start(sp_x, False, False, 0)
        coord_box.pack_start(Gtk.Label(label="  Y座標:"), False, False, 0)
        coord_box.pack_start(sp_y, False, False, 0)
        pos_box.pack_start(coord_box, False, False, 0)

        def update_align_sensitivity(*_args):
            ar = chk_right.get_active()
            sp_margin.set_sensitive(ar)
            sp_x.set_sensitive(not ar)

        chk_right.connect("toggled", update_align_sensitivity)
        update_align_sensitivity()

        grid.attach(lbl_pos, 0, row, 1, 1)
        grid.attach(pos_box, 1, row, 2, 1)

        row += 1
        lbl_op = Gtk.Label(label="透過度（不透明度 %）:", xalign=0)
        sc_op = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 50, 100, 1)
        sc_op.set_value(int(slot.get("opacity", 88)))
        sc_op.set_value_pos(Gtk.PositionType.RIGHT)
        sc_op.set_hexpand(True)
        grid.attach(lbl_op, 0, row, 1, 1)
        grid.attach(sc_op, 1, row, 2, 1)

        row += 1
        lbl_rad = Gtk.Label(label="角丸（px）:", xalign=0)
        sp_rad = Gtk.SpinButton.new_with_range(0, 25, 1)
        sp_rad.set_value(int(slot.get("corner_radius", 20)))
        sp_rad.set_halign(Gtk.Align.START)
        grid.attach(lbl_rad, 0, row, 1, 1)
        grid.attach(sp_rad, 1, row, 1, 1)

        btn_row = Gtk.Box(spacing=10)
        btn_login = Gtk.Button(label="このアプリを通常ブラウザで開いてログイン / 拡張設定")
        btn_login.connect("clicked", self._on_login_clicked, slot["id"])
        btn_row.pack_start(btn_login, False, False, 0)
        vbox.pack_start(btn_row, False, False, 6)

        self.slot_controls.append({
            "slot": slot,
            "enabled": sw_en,
            "name": ent_name,
            "url": ent_url,
            "width": sp_w,
            "height": sp_h,
            "align_right": chk_right,
            "right_margin": sp_margin,
            "x": sp_x,
            "y": sp_y,
            "opacity": sc_op,
            "corner_radius": sp_rad,
        })
        return vbox

    def _on_preset_clicked(self, _btn, ent_name, ent_url, p_name, p_url):
        ent_name.set_text(p_name)
        ent_url.set_text(p_url)

    def _on_login_clicked(self, _btn, slot_id):
        self.status_label.set_text("通常ブラウザでログイン画面を開いています...")
        subprocess.Popen(["python3", MANAGER_BIN, "login", slot_id])

    def collect_and_save(self):
        for ctrl in self.slot_controls:
            s = ctrl["slot"]
            s["enabled"] = ctrl["enabled"].get_active()
            s["name"] = ctrl["name"].get_text().strip() or s["id"]
            s["url"] = ctrl["url"].get_text().strip() or s["url"]
            s["width"] = int(ctrl["width"].get_value())
            s["height"] = int(ctrl["height"].get_value())
            s["align_right"] = ctrl["align_right"].get_active()
            s["right_margin"] = int(ctrl["right_margin"].get_value())
            s["x"] = int(ctrl["x"].get_value())
            s["y"] = int(ctrl["y"].get_value())
            s["opacity"] = int(ctrl["opacity"].get_value())
            s["corner_radius"] = int(ctrl["corner_radius"].get_value())

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def save_and_apply(self, restart_urls=False):
        self.collect_and_save()
        self.btn_apply.set_sensitive(False)
        self.btn_restart.set_sensitive(False)
        self.status_label.set_text("デスクトップへ反映中...")

        def worker():
            cmd = ["python3", MANAGER_BIN, "apply"]
            if restart_urls:
                cmd.append("--restart-urls")
            res = subprocess.run(cmd, capture_output=True, text=True)
            GLib.idle_add(self._on_apply_done, res.returncode == 0, res.stderr.strip())

        threading.Thread(target=worker, daemon=True).start()

    def _on_apply_done(self, ok, err):
        self.btn_apply.set_sensitive(True)
        self.btn_restart.set_sensitive(True)
        if ok:
            self.status_label.set_text("反映しました！")
        else:
            self.status_label.set_text(f"エラー: {err or '反映に失敗しました'}")
        return False


def main():
    check_only = "--check" in sys.argv[1:]
    win = WidgetSettingsWindow()
    if check_only:
        win.destroy()
        print("GTK_SETTINGS_CHECK_OK")
        return
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
