#!/usr/bin/env bash
export DISPLAY="${DISPLAY:-:0}"
xmodmap -e "clear Lock" 2>/dev/null || true
xmodmap -e "keycode 66 = Eisu_toggle Caps_Lock Eisu_toggle Caps_Lock" 2>/dev/null || true
