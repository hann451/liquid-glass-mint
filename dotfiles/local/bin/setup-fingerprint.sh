#!/usr/bin/env bash
set -euo pipefail

DEB_DIR="__USER_HOME__/.cache/liquid-glass/goodix-fprint"
BASE_URL="https://github.com/simplenty/libfprint-driver-for-goodix-27c6-550a/releases/download/0.0.1"

echo "=== Goodix 指紋認証センサー (27c6:550a) セットアップ ==="
if ! lsusb | grep -qi "27c6:550a"; then
    echo "警告: lsusb で 27c6:550a が見つかりませんでした。お使いのセンサーを確認します:"
    lsusb | grep -iE 'finger|goodix|synaptics|elan|validity' || true
fi

mkdir -p "$DEB_DIR"
if [ ! -f "$DEB_DIR/libfprint-2-tod-goodix_amd64.deb" ]; then
    echo "ドライバパッケージをダウンロード中..."
    curl -fsSL -o "$DEB_DIR/libfprint-2-tod-goodix_amd64.deb" "$BASE_URL/libfprint-2-tod-goodix_amd64.deb"
    curl -fsSL -o "$DEB_DIR/libfprint-2-tod1_amd64.deb" "$BASE_URL/libfprint-2-tod1_1.94.7+tod1-0ubuntu5.24.04.4_amd64.deb"
    curl -fsSL -o "$DEB_DIR/libfprint-2-2_amd64.deb" "$BASE_URL/libfprint-2-2_1.94.9+tod1-1_amd64.deb"
fi

echo "[1/4] Goodix TOD ドライバを導入中（パスワードを入力してください）..."
sudo dpkg -i "$DEB_DIR/libfprint-2-tod-goodix_amd64.deb" || true
sudo apt-get install -f -y
sudo systemctl restart fprintd
sleep 1

if fprintd-list "$USER" 2>&1 | grep -qi "No devices available"; then
    echo "互換 tod1 ライブラリを追加適用中..."
    sudo dpkg -i "$DEB_DIR/libfprint-2-tod1_amd64.deb" "$DEB_DIR/libfprint-2-2_amd64.deb" "$DEB_DIR/libfprint-2-tod-goodix_amd64.deb" || true
    sudo apt-get install -f -y
    sudo systemctl restart fprintd
    sleep 1
fi

echo "[2/4] センサー認識確認:"
fprintd-list "$USER"

echo "[3/4] ログイン・画面ロック・sudo で指紋認証を有効化中..."
sudo pam-auth-update --enable fprintd

echo "[4/4] 指紋を登録します！画面の指示に従って指紋センサーに同じ指を数回タッチしてください..."
fprintd-enroll

echo ""
echo "登録確認テストを行います（指を1回センサーにタッチしてください）:"
fprintd-verify || true

echo ""
echo "=== 指紋認証のセットアップが完了しました！ ==="
