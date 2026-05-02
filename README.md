# RPi Camera DVR

Add **Twitch / YouTube-Live class DVR (time-shift) playback** to a Raspberry Pi IP camera (IMX219 / Pi Camera Module).

Watch live on a phone, drag the seek bar left to scrub back to broadcast start (or last N hours), hover for thumbnail preview, tap **LIVE** to snap to the edge — the same UX as Chzzk / Twitch / YouTube Live, served entirely off-grid from a Raspberry Pi with SD-card storage.

```
[IMX219] → [RPi] → ffmpeg HLS muxer → SD card (.ts segments + thumbs)
                          │
                          ▼
                       nginx (:8090)
                          │
                          ▼
                Phone (hls.js + Plyr, via Tailscale)
```

## Status

**2026-05-02 — Planning.** Specification and roadmap done. Implementation not started.

See **[docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md)** for full details: architecture, ffmpeg pipelines for RPi 3B (HW H.264) and RPi 5 (SW libx264), LL-HLS configuration, WebVTT thumbnail sprite generation, SD-card retention policy, the 6-phase roadmap, and a curated reference list (RFC 8216, Apple LL-HLS, hls.js / Plyr, plus academic surveys on HTTP adaptive streaming).

## Open decisions

- [ ] Board: RPi 3B (720p / 4 h retention) or wait for RPi 5 (1080p / 24 h+)
- [ ] Retention window: 1 h / 4 h / 24 h / since-broadcast-start
- [ ] Recording trigger: always-on while booted, or phone "Start broadcast" button
- [ ] Player: hls.js + Plyr (default) / video.js / Shaka
- [ ] LL-HLS on or off
- [ ] Storage: SD only / SD + USB SSD or NVMe HAT
- [ ] Auth: Tailscale-only / explicit token

## Roadmap (high level)

1. **MVP** — libcamera-vid → ffmpeg HLS → nginx → static hls.js player. Phone seeks back 1 h.
2. **Thumbnail hover** — WebVTT sprite track.
3. **Retention** — cron cleanup, SD usage monitoring.
4. **UX polish** — LIVE badge, absolute clock, PWA install.
5. **(optional) AI event markers** — Jetson Orin YOLOv8 → webhook → seekbar markers.
6. **(optional) RPi 5 migration** — 1080p30 LL-HLS, NVMe HAT, dual IMX219.

## Related

This project is a sibling to [Multi-Board-Viewer](https://github.com/squid55/Multi-Board-Viewer); it adds a DVR layer specific to the Raspberry Pi camera node and does not depend on the multiboard viewer to run.

## License

TBD.
