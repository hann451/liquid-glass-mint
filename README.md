# Liquid Glass Mint — macOS風リキッドグラス × 実用デスクトップ構築キット

Linux Mint（Cinnamon / X11）を、macOS風の美しい **Liquid Glass（すりガラス）デザイン** と **デスクトップ常駐の実用ウィジェット** を備えたホーム画面へ1コマンドでセットアップできる構築キットです。

> **プライバシー保護**：設定同期スクリプト（`sync-from-current.sh`）および `.gitignore` により、ブラウザプロファイル（Notion / TimeTree 等のログインセッション）、パスワード、ユーザー固有パス、一時キャッシュは公開対象から完全に除外されます。

---

## 主な特徴

- **macOS風ベースUI ＆ 本物のすりガラスブラー**
  - 上部メニューバー（28px）＋ 下部ライトガラス調フローティングドック（Plank）
  - **Blur Cinnamon** によるパネル・メニュー・通知・オーバービューのすりガラス効果
  - **WhiteSur**（glassy）ダークテーマ・アイコン・カーソル、ウィンドウボタン左配置、デスクトップアイコン非表示
- **左側：Conky + Lua (Cairo) リキッドグラスカード（3枚構成）**
  - **時計・日付・天気**：Open-Meteo API（APIキー不要）で現在気温と天気を自動取得
  - **SYSTEM STATUS**：CPU / メモリ / SSD / CPU温度（`k10temp`・`coretemp` 等対応）のリアルタイムバー
  - **NOW PLAYING**：`playerctl`（MPRIS）連携で **YouTube / YouTube Music / Spotify** の再生中サムネイル・曲名・チャンネル名・再生位置バーを表示
- **右側：枠なし常駐 Web ウィジェット（Notion / TimeTree / カスタム）**
  - 壁紙上から直接入力・操作できる Notion（大サイズ）と TimeTree カレンダーを常駐
  - モニター解像度を `xrandr` で自動検出し、別PCでも崩れず自動配置
- **日本語 GUI 設定アプリ（デスクトップウィジェット設定）**
  - URL・サイズ（幅/高さ）・位置・透過度・角丸・表示 ON/OFF（最大3枠）をGUIからいつでも変更可能
- **実用ユーティリティ**
  - **Ulauncher**：`Alt + Space` で Spotlight 風クイック検索（リキッドグラステーマ）
  - **Cinnamenu / Spicy Clipboard / gTile / ホットコーナー / ナイトライト** を標準組み込み

---

## 対象環境

- **OS**: Linux Mint 22.x（Cinnamon デスクトップ環境）
- **セッション**: 通常の **Cinnamon (X11)** セッション（※Plank / Devilspie2 安定動作のため）
- **Webウィジェット用ブラウザ**: Google Chrome または Chromium（未導入時は `install.sh` が Chromium の導入を試みます）

---

## 1コマンドインストール（新しいPCでのセットアップ）

```bash
git clone https://github.com/hann451/liquid-glass-mint.git ~/liquid-glass-mint
cd ~/liquid-glass-mint
./install.sh
```

> 途中の `apt install` のタイミングでパスワード入力を求められます。インストール完了後、テーマやドック・ウィジェットが自動で起動します。

---

## セットアップ後の使い方

- **ウィジェットのURLやサイズを変えたいとき**
  - ドックの「デスクトップウィジェット設定」アイコン、または `Alt + Space`（Ulauncher）から **「デスクトップウィジェット設定」** を開いて変更できます。
  - Notion や TimeTree へ初回ログインする際は、そのまま画面上でログインするか、設定画面内の **「このアプリを通常ブラウザで開いてログイン」** ボタンを使うとスムーズです。
- **YouTube で音楽再生連動を使う**
  - ドックの **YouTube Music** アイコン、または Chrome で YouTube を再生すると左下の **NOW PLAYING** カードが自動で更新されます。
- **天気の地域を変えたいとき**
  - `~/.config/conky/scripts/config.json` の `latitude` / `longitude` / `location_name` を編集してください（デフォルトは Tokyo）。
- **ドックに好きなアプリを追加する**
  - アプリ起動中にドック上のアイコンを右クリック →「ドックに固定」するか、メニューからドックへドラッグ＆ドロップしてください。

---

## このPCの変更をリポジトリへ同期する

壁紙・ウィジェット設定・ドック構成などを変更したあと、他PC向けにエクスポートするときは以下を実行します：

```bash
cd ~/liquid-glass-mint
./sync-from-current.sh
```

---

## クレジット（外部OSS・API）

本キットの `install.sh` は以下の素晴らしいオープンソースソフトウェアおよびAPIを導入・利用しています：

- [WhiteSur-gtk-theme](https://github.com/vinceliuice/WhiteSur-gtk-theme) / [WhiteSur-icon-theme](https://github.com/vinceliuice/WhiteSur-icon-theme) / [WhiteSur-cursors](https://github.com/vinceliuice/WhiteSur-cursors) by vinceliuice
- [Blur Cinnamon](https://github.com/klangman/BlurCinnamon) (`BlurCinnamon@klangman`), `gTile@shuairan`, `Cinnamenu@json`, `spicy-clipboard-applet@Twilight0` (Cinnamon Spices)
- Conky, Plank, Devilspie2, Ulauncher, playerctl
- Weather data by [Open-Meteo](https://open-meteo.com/)

License: MIT (see [LICENSE](LICENSE))
