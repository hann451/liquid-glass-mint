#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
MGR="$HOME/.local/bin/desktop-widgets-manager.py"

case "${1:-}" in
    --align)
        exec python3 "$MGR" align
        ;;
    --restart)
        exec python3 "$MGR" apply --restart-urls
        ;;
    --stop)
        exec python3 "$MGR" stop
        ;;
    --login)
        exec python3 "$MGR" login "${2:-}"
        ;;
    --focus)
        exec python3 "$MGR" focus "${2:-slot1}"
        ;;
    --focus-notion)
        exec python3 "$MGR" focus slot1
        ;;
    --focus-timetree)
        exec python3 "$MGR" focus slot2
        ;;
    --youtube-music)
        exec python3 "$MGR" youtube-music
        ;;
    *)
        exec python3 "$MGR" apply
        ;;
esac
