#!/bin/zsh
set -eu
board_studio_root="${0:A:h}"
exec /usr/bin/python3 "$board_studio_root/launch.py" "$@"
