#!/usr/bin/env python3
"""Trim HLS playlist: drop entries whose .ts file no longer exists.

ffmpeg with -hls_list_size 0 never prunes; we delete .ts files via cron
and run this to keep dvr.m3u8 in sync. Safe to race with ffmpeg writes
because ffmpeg rewrites the playlist on every new segment anyway.
"""
import os
import sys


META_PREFIXES = (
    "#EXTINF",
    "#EXT-X-PROGRAM-DATE-TIME",
    "#EXT-X-BYTERANGE",
    "#EXT-X-DISCONTINUITY",
    "#EXT-X-KEY",
    "#EXT-X-MAP",
)


def trim(path):
    if not os.path.exists(path):
        return
    base = os.path.dirname(path)
    with open(path, "r") as f:
        lines = f.read().splitlines()

    out = []
    pending = []
    for line in lines:
        if line.startswith(META_PREFIXES):
            pending.append(line)
            continue
        if not line or line.startswith("#"):
            if pending:
                out.extend(pending)
                pending = []
            out.append(line)
            continue
        seg = os.path.join(base, line)
        if os.path.exists(seg):
            out.extend(pending)
            out.append(line)
        pending = []

    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        trim(arg)
