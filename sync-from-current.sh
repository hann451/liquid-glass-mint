#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOT="$SCRIPT_DIR/dotfiles"

rm -rf "$DOT"
mkdir -p \
  "$DOT/config/conky/scripts" \
  "$DOT/config/devilspie2" \
  "$DOT/config/desktop-widgets" \
  "$DOT/config/plank/dock1/launchers" \
  "$DOT/config/ulauncher/user-themes/liquid-glass" \
  "$DOT/config/autostart" \
  "$DOT/config/cinnamon-spices/BlurCinnamon@klangman" \
  "$DOT/config/cinnamon-spices/Cinnamenu@json" \
  "$DOT/config/cinnamon-spices/spicy-clipboard-applet@Twilight0" \
  "$DOT/local/share/plank/themes/LiquidGlass" \
  "$DOT/local/share/applications" \
  "$DOT/local/bin" \
  "$DOT/Pictures/Wallpapers"

# Conky + Lua + Python scripts (sanitizing Gmail credentials)
cp "$HOME/.config/conky/glass.conf" "$DOT/config/conky/"
cp "$HOME/.config/conky/glass.lua" "$DOT/config/conky/"
cp "$HOME/.config/conky/scripts/fetch_weather.py" "$DOT/config/conky/scripts/"
cp "$HOME/.config/conky/scripts/fetch_status.py" "$DOT/config/conky/scripts/"
python3 - <<PY
import json
src = "$HOME/.config/conky/scripts/config.json"
dst = "$DOT/config/conky/scripts/config.json"
with open(src, "r", encoding="utf-8") as f:
    cfg = json.load(f)
if isinstance(cfg.get("gmail"), dict):
    cfg["gmail"]["enabled"] = False
    cfg["gmail"]["email"] = ""
with open(dst, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=4, ensure_ascii=False)
PY

# Devilspie2 & Desktop Web Widget configs (never copy browser profile dirs or legacy urls.conf)
cp "$HOME/.config/devilspie2/desktop_widgets.lua" "$DOT/config/devilspie2/"
[ -f "$HOME/.config/desktop-widgets/widgets.json" ] && cp "$HOME/.config/desktop-widgets/widgets.json" "$DOT/config/desktop-widgets/"
cp "$HOME/.config/desktop-widgets/stylus-liquid-glass.css" "$DOT/config/desktop-widgets/"

# Plank theme & launchers
cp "$HOME/.local/share/plank/themes/LiquidGlass/dock.theme" "$DOT/local/share/plank/themes/LiquidGlass/"
cp "$HOME/.config/plank/dock1/launchers/"*.dockitem "$DOT/config/plank/dock1/launchers/"

# Ulauncher theme & settings (exclude runtime-generated generated.css)
cp "$HOME/.config/ulauncher/settings.json" "$DOT/config/ulauncher/"
for f in manifest.json theme.css theme-gtk-3.20.css; do
    [ -f "$HOME/.config/ulauncher/user-themes/liquid-glass/$f" ] && \
        cp "$HOME/.config/ulauncher/user-themes/liquid-glass/$f" "$DOT/config/ulauncher/user-themes/liquid-glass/"
done

# Autostart entries
for f in plank.desktop devilspie2.desktop ulauncher.desktop conky-liquid-glass.desktop desktop-widgets.desktop; do
    [ -f "$HOME/.config/autostart/$f" ] && cp "$HOME/.config/autostart/$f" "$DOT/config/autostart/"
done

# Custom app launchers & management scripts
for f in youtube-music.desktop notion-widget.desktop timetree-widget.desktop desktop-widgets-settings.desktop; do
    [ -f "$HOME/.local/share/applications/$f" ] && cp "$HOME/.local/share/applications/$f" "$DOT/local/share/applications/"
done
cp "$HOME/.local/bin/launch-desktop-widgets.sh" "$DOT/local/bin/"
cp "$HOME/.local/bin/desktop-widgets-manager.py" "$DOT/local/bin/"
cp "$HOME/.local/bin/desktop-widgets-settings.py" "$DOT/local/bin/"

# Cinnamon Spices settings (sanitize Cinnamenu recent-apps)
[ -f "$HOME/.config/cinnamon/spices/BlurCinnamon@klangman/BlurCinnamon@klangman.json" ] && \
    cp "$HOME/.config/cinnamon/spices/BlurCinnamon@klangman/BlurCinnamon@klangman.json" "$DOT/config/cinnamon-spices/BlurCinnamon@klangman/"
if [ -f "$HOME/.config/cinnamon/spices/Cinnamenu@json/20.json" ]; then
    python3 - <<PY
import json
src = "$HOME/.config/cinnamon/spices/Cinnamenu@json/20.json"
dst = "$DOT/config/cinnamon-spices/Cinnamenu@json/20.json"
with open(src, "r", encoding="utf-8") as f:
    cm = json.load(f)
if isinstance(cm.get("recent-apps"), dict):
    cm["recent-apps"]["value"] = []
with open(dst, "w", encoding="utf-8") as f:
    json.dump(cm, f, indent=4, ensure_ascii=False)
PY
fi
[ -f "$HOME/.config/cinnamon/spices/spicy-clipboard-applet@Twilight0/spicy-clipboard-applet@Twilight0.json" ] && \
    cp "$HOME/.config/cinnamon/spices/spicy-clipboard-applet@Twilight0/spicy-clipboard-applet@Twilight0.json" "$DOT/config/cinnamon-spices/spicy-clipboard-applet@Twilight0/"

# Original Liquid Glass wallpaper only
[ -f "$HOME/Pictures/Wallpapers/LiquidGlass-Wave.png" ] && \
    cp "$HOME/Pictures/Wallpapers/LiquidGlass-Wave.png" "$DOT/Pictures/Wallpapers/"

# Normalize hardcoded user home path to __USER_HOME__ for portability
find "$DOT" -type f \( -name '*.conf' -o -name '*.lua' -o -name '*.py' -o -name '*.sh' -o -name '*.desktop' -o -name '*.dockitem' -o -name '*.json' -o -name '*.css' \) -exec sed -i "s|$HOME|__USER_HOME__|g" {} +

echo "同期完了: $DOT に公開用設定を保存しました（個人情報・キャッシュ・サードパーティ壁紙を除外済み）。"
