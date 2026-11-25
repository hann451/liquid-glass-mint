#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOT="$SCRIPT_DIR/dotfiles"
export DISPLAY="${DISPLAY:-:0}"

if [ ! -d "$DOT" ]; then
    echo "Error: dotfiles ディレクトリが見つかりません: $DOT" >&2
    exit 1
fi

echo "=== Linux Mint リキッドグラス × macOS風デスクトップ セットアップ ==="
if [ "${XDG_SESSION_TYPE:-x11}" = "wayland" ]; then
    echo "警告: Wayland セッションが検出されました。Plank / Devilspie2 のため通常の Cinnamon (X11) セッションをおすすめします。"
fi

echo "[1/7] 必要パッケージを導入中..."
sudo apt update
sudo apt install -y git curl unzip sassc libglib2.0-dev-bin libxml2-utils \
    plank conky-all devilspie2 wmctrl xdotool jq playerctl fonts-inter \
    python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gdkpixbuf-2.0

if ! command -v google-chrome-stable >/dev/null 2>&1 && ! command -v google-chrome >/dev/null 2>&1 && ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
    echo "Chromium系ブラウザをインストール中..."
    sudo apt install -y chromium || sudo apt install -y chromium-browser || true
fi

if ! command -v ulauncher >/dev/null 2>&1; then
    echo "Ulauncher をダウンロード・導入中..."
    ULAUNCHER_URL="$(curl -fsSL https://api.github.com/repos/Ulauncher/Ulauncher/releases/latest | python3 -c "import sys,json; d=json.load(sys.stdin); print(next(a['browser_download_url'] for a in d.get('assets',[]) if a['name'].endswith('.deb')))")"
    curl -fsSL -o /tmp/ulauncher_latest.deb "$ULAUNCHER_URL"
    sudo apt install -y /tmp/ulauncher_latest.deb
    rm -f /tmp/ulauncher_latest.deb
fi

echo "[2/7] WhiteSur テーマ・アイコン・カーソルを導入中..."
TMP_SRC="/tmp/whitesur-build-$$"
mkdir -p "$TMP_SRC" "$HOME/.themes" "$HOME/.local/share/icons"
git clone --depth=1 https://github.com/vinceliuice/WhiteSur-gtk-theme.git "$TMP_SRC/WhiteSur-gtk-theme"
git clone --depth=1 https://github.com/vinceliuice/WhiteSur-icon-theme.git "$TMP_SRC/WhiteSur-icon-theme"
git clone --depth=1 https://github.com/vinceliuice/WhiteSur-cursors.git "$TMP_SRC/WhiteSur-cursors"

"$TMP_SRC/WhiteSur-gtk-theme/install.sh" -d "$HOME/.themes" -N glassy -l -c Dark
"$TMP_SRC/WhiteSur-icon-theme/install.sh" -d "$HOME/.local/share/icons" -t default
rm -rf "$HOME/.local/share/icons/WhiteSur-cursors"
cp -pr "$TMP_SRC/WhiteSur-cursors/dist" "$HOME/.local/share/icons/WhiteSur-cursors"
rm -rf "$TMP_SRC"

echo "[3/7] Cinnamon Spices (拡張・アプレット) を導入中..."
python3 - <<'PY'
import urllib.request, zipfile, io, os
base = os.path.expanduser('~/.local/share/cinnamon')
items = [
    ('extensions', 'BlurCinnamon@klangman'),
    ('extensions', 'gTile@shuairan'),
    ('applets', 'Cinnamenu@json'),
    ('applets', 'spicy-clipboard-applet@Twilight0'),
]
for kind, uuid in items:
    dest = os.path.join(base, kind)
    os.makedirs(dest, exist_ok=True)
    url = f'https://cinnamon-spices.linuxmint.com/files/{kind}/{uuid}.zip'
    data = urllib.request.urlopen(url, timeout=20).read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(dest)
PY

echo "[4/7] 設定ファイルと壁紙を配置し、画面解像度に合わせて同期中..."
mkdir -p \
  "$HOME/.config/conky/scripts" \
  "$HOME/.config/devilspie2" \
  "$HOME/.config/desktop-widgets" \
  "$HOME/.config/plank/dock1/launchers" \
  "$HOME/.config/ulauncher/user-themes/liquid-glass" \
  "$HOME/.config/autostart" \
  "$HOME/.config/cinnamon/spices/BlurCinnamon@klangman" \
  "$HOME/.config/cinnamon/spices/Cinnamenu@json" \
  "$HOME/.config/cinnamon/spices/spicy-clipboard-applet@Twilight0" \
  "$HOME/.config/fcitx5" \
  "$HOME/.config/mozc" \
  "$HOME/.local/share/plank/themes/LiquidGlass" \
  "$HOME/.local/share/applications" \
  "$HOME/.local/bin" \
  "$HOME/.cache/liquid-glass" \
  "$HOME/Pictures/Wallpapers"

cp -r "$DOT/config/conky/." "$HOME/.config/conky/"
cp -r "$DOT/config/devilspie2/." "$HOME/.config/devilspie2/"
cp -r "$DOT/config/desktop-widgets/." "$HOME/.config/desktop-widgets/"
cp -r "$DOT/config/plank/dock1/launchers/." "$HOME/.config/plank/dock1/launchers/"
cp -r "$DOT/config/ulauncher/." "$HOME/.config/ulauncher/"
cp -r "$DOT/config/autostart/." "$HOME/.config/autostart/"
cp -r "$DOT/config/cinnamon-spices/." "$HOME/.config/cinnamon/spices/"
[ -d "$DOT/config/fcitx5" ] && cp -r "$DOT/config/fcitx5/." "$HOME/.config/fcitx5/"
[ -d "$DOT/config/mozc" ] && cp -r "$DOT/config/mozc/." "$HOME/.config/mozc/"
cp -r "$DOT/local/share/plank/themes/LiquidGlass/." "$HOME/.local/share/plank/themes/LiquidGlass/"
cp -r "$DOT/local/share/applications/." "$HOME/.local/share/applications/"
cp -r "$DOT/local/bin/." "$HOME/.local/bin/"
cp -r "$DOT/Pictures/Wallpapers/." "$HOME/Pictures/Wallpapers/"

for target in \
  "$HOME/.config/conky" \
  "$HOME/.config/devilspie2" \
  "$HOME/.config/desktop-widgets" \
  "$HOME/.config/plank/dock1/launchers" \
  "$HOME/.config/ulauncher" \
  "$HOME/.config/autostart" \
  "$HOME/.config/cinnamon/spices" \
  "$HOME/.config/fcitx5" \
  "$HOME/.config/mozc" \
  "$HOME/.local/share/applications" \
  "$HOME/.local/bin"; do
    find "$target" -type f -exec sed -i "s|__USER_HOME__|$HOME|g" {} +
done

chmod +x "$HOME/.config/conky/scripts/"*.py "$HOME/.local/bin/"*
python3 "$HOME/.local/bin/desktop-widgets-manager.py" sync-configs
[ -f "$HOME/.config/mozc/setup_mozc_smart.py" ] && python3 "$HOME/.config/mozc/setup_mozc_smart.py" || true
[ -x "$HOME/.local/bin/setup-keyboard-ime.sh" ] && "$HOME/.local/bin/setup-keyboard-ime.sh" || true

echo "[5/7] Cinnamon と Plank 設定を適用中..."
gsettings set org.cinnamon.theme name 'WhiteSur-Dark'
gsettings set org.cinnamon.desktop.interface gtk-theme 'WhiteSur-Dark'
gsettings set org.cinnamon.desktop.wm.preferences theme 'WhiteSur-Dark'
gsettings set org.cinnamon.desktop.interface icon-theme 'WhiteSur'
gsettings set org.cinnamon.desktop.interface cursor-theme 'WhiteSur-cursors'
gsettings set org.cinnamon.desktop.wm.preferences button-layout 'close,minimize,maximize:'
gsettings set org.cinnamon.desktop.interface font-name 'Inter 10'
gsettings set org.cinnamon.desktop.wm.preferences titlebar-font 'Inter Bold 10'
gsettings set org.cinnamon.desktop.background picture-uri "file://$HOME/Pictures/Wallpapers/LiquidGlass-Wave.png"

gsettings set org.nemo.desktop show-desktop-icons false
gsettings set org.nemo.desktop computer-icon-visible false
gsettings set org.nemo.desktop home-icon-visible false
gsettings set org.nemo.desktop trash-icon-visible false
gsettings set org.nemo.desktop volumes-visible false
gsettings set org.nemo.desktop network-icon-visible false

gsettings set org.cinnamon enabled-desklets "[]"
gsettings set org.cinnamon enabled-extensions "['BlurCinnamon@klangman', 'gTile@shuairan']"
gsettings set org.cinnamon panels-enabled "['1:0:top']"
gsettings set org.cinnamon panels-height "['1:28']"
gsettings set org.cinnamon panels-autohide "['1:false']"
gsettings set org.cinnamon panel-zone-icon-sizes '[{"panelId": 1, "left": 18, "center": 18, "right": 18}]'
gsettings set org.cinnamon enabled-applets "['panel1:left:0:Cinnamenu@json:20', 'panel1:center:0:calendar@cinnamon.org:13', 'panel1:right:0:systray@cinnamon.org:3', 'panel1:right:1:xapp-status@cinnamon.org:4', 'panel1:right:2:spicy-clipboard-applet@Twilight0:21', 'panel1:right:3:notifications@cinnamon.org:5', 'panel1:right:4:removable-drives@cinnamon.org:7', 'panel1:right:5:keyboard@cinnamon.org:8', 'panel1:right:6:network@cinnamon.org:10', 'panel1:right:7:sound@cinnamon.org:11', 'panel1:right:8:power@cinnamon.org:12']"
gsettings set org.cinnamon hotcorner-layout "['scale:true:150', 'expo:true:150', 'expo:false:0', 'desktop:false:0']"
gsettings set org.cinnamon.settings-daemon.plugins.color night-light-enabled true
gsettings set org.cinnamon.settings-daemon.plugins.color night-light-schedule-mode 'auto'
gsettings set org.cinnamon.settings-daemon.plugins.color night-light-temperature 3700
gsettings set org.cinnamon.gestures enabled true
gsettings set org.cinnamon.gestures swipe-percent-threshold 35
gsettings set org.cinnamon.gestures swipe-right-3 'EXEC::xdotool key ctrl+Next::end'
gsettings set org.cinnamon.gestures swipe-left-3 'EXEC::xdotool key ctrl+Prior::end'

DOCK_LIST=()
for f in 01-nemo.dockitem 02-applications.dockitem 03-google-chrome.dockitem 04-vscode.dockitem 05-terminal.dockitem 06-youtube-music.dockitem 07-notion.dockitem 08-timetree.dockitem 09-settings.dockitem 09b-widget-settings.dockitem 10-trash.dockitem; do
    p="$HOME/.config/plank/dock1/launchers/$f"
    [ -f "$p" ] || continue
    launcher=$(awk -F= '/^Launcher=/{print $2}' "$p" | sed 's|^file://||')
    if [[ "$launcher" == docklet://* ]] || [ -f "$launcher" ]; then
        DOCK_LIST+=("'$f'")
    fi
done
DOCK_STR="[$(IFS=,; echo "${DOCK_LIST[*]}")]"

pkill -x plank 2>/dev/null || true
sleep 0.5
dconf write /net/launchpad/plank/enabled-docks "['dock1']"
dconf write /net/launchpad/plank/docks/dock1/position "'bottom'"
dconf write /net/launchpad/plank/docks/dock1/alignment "'center'"
dconf write /net/launchpad/plank/docks/dock1/theme "'LiquidGlass'"
dconf write /net/launchpad/plank/docks/dock1/zoom-enabled "true"
dconf write /net/launchpad/plank/docks/dock1/zoom-percent "140"
dconf write /net/launchpad/plank/docks/dock1/icon-size "46"
dconf write /net/launchpad/plank/docks/dock1/hide-mode "'intelligent'"
dconf write /net/launchpad/plank/docks/dock1/dock-items "$DOCK_STR"

echo "[6/7] 初期データ取得 ＆ Cinnamon リロード中..."
python3 "$HOME/.config/conky/scripts/fetch_weather.py" --force || true
python3 "$HOME/.config/conky/scripts/fetch_status.py" || true
dbus-send --session --dest=org.Cinnamon --type=method_call /org/Cinnamon org.Cinnamon.RestartCinnamon boolean:false || true
sleep 3

echo "[7/7] Plank / Devilspie2 / Ulauncher / Conky / Webウィジェットを起動中..."
pkill -x plank 2>/dev/null || true
pkill -x devilspie2 2>/dev/null || true
pkill -x conky 2>/dev/null || true
pkill -f '/usr/bin/ulauncher' 2>/dev/null || true
sleep 1
setsid plank >/dev/null 2>&1 &
setsid devilspie2 >/dev/null 2>&1 &
setsid ulauncher --hide-window >/dev/null 2>&1 &
setsid conky -c "$HOME/.config/conky/glass.conf" >/dev/null 2>&1 &
sleep 1
python3 "$HOME/.local/bin/desktop-widgets-manager.py" apply

echo "=== 完了！新しいPCでも同じデスクトップ環境が構築されました ==="
