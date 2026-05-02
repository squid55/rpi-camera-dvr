#!/bin/bash
# Removes DVR HLS segments and thumbnails older than RETAIN_HOURS,
# then trims dvr.m3u8 to drop entries pointing to deleted segments.
set -u
RETAIN_HOURS="${RETAIN_HOURS:-4}"
DVR_DIR="${DVR_DIR:-/srv/dvr}"

find "$DVR_DIR" -maxdepth 1 -name 'seg_*.ts' \
    -mmin +$((RETAIN_HOURS * 60)) -delete
[ -d "$DVR_DIR/thumbs" ] && find "$DVR_DIR/thumbs" -name 'sprite_*.jpg' \
    -mmin +$((RETAIN_HOURS * 60 + 30)) -delete

[ -f "$DVR_DIR/dvr.m3u8" ] && /usr/local/bin/trim_m3u8.py "$DVR_DIR/dvr.m3u8"
