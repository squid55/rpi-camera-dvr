# RPi Camera DVR — Implementation Plan

> Created: 2026-05-02
> Goal: Twitch/YouTube-Live class **DVR (time-shift) playback** on a Raspberry Pi IP camera (IMX219 / Pi Camera Module)
> Storage: SD card (option: USB SSD / NVMe HAT on RPi 5)

---

## 1. Overview

### 1.1 One-line summary
Watch the RPi camera live on a phone, drag the seek bar left to scrub back to **broadcast start (or last N hours)**, hover for **thumbnail preview**, tap **LIVE** to snap to the current edge — i.e. the same UX as Chzzk / Twitch / YouTube Live, served entirely off-grid from one RPi.

### 1.2 Why
Existing single-stream Pi setups (libcamera-vid → MJPEG / RTSP) are **live-only**. Past footage is unrecoverable. Adding a DVR layer turns the Pi camera into a "blackbox + live" device in one.

---

## 2. Target UX (Chzzk reference)

| Element | Behavior |
|---|---|
| Red **LIVE** badge | Shown when playhead matches `liveSyncPosition` |
| **Drag seek bar to leftmost** | Jump to broadcast start or retention boundary |
| **Hover preview** | WebVTT thumbnail track shown above the cursor |
| **"LIVE" button** | `video.currentTime = hls.liveSyncPosition` |
| Pause / speed / fullscreen | Standard video controls |
| Time offset display | `-06:48` style relative-to-live caption |

---

## 3. Architecture

```
[IMX219 Camera]
       │
       ▼ MIPI CSI
[RPi 3B or RPi 5]
  ├── libcamera-vid / ffmpeg  (H.264 encode)
  ├── ffmpeg HLS muxer
  │     ├── dvr.m3u8           (full DVR playlist)
  │     ├── seg_00001.ts ...   (2 s segments on SD)
  │     └── thumbs/
  │           ├── sprite_0001.jpg (10x10 = 100 thumbs/sheet)
  │           └── thumbs.vtt
  ├── cleanup cron             (drop segments past retention window)
  └── nginx (static, :8090)
       │
       ▼ Tailscale (or LAN)
[Phone Browser]
  ├── hls.js + Plyr
  ├── LIVE button / seek bar / VTT thumbnail hover
  └── Optional PWA install
```

---

## 4. Components

### 4.1 Capture + H.264 encode

**RPi 3B (HW encoder — VideoCore IV)**
```bash
libcamera-vid -t 0 --width 1280 --height 720 --framerate 30 \
  --codec h264 --bitrate 1500000 --inline -o - | \
  ffmpeg -fflags nobuffer -i - \
    -c:v copy -an \
    -f hls \
    -hls_time 2 \
    -hls_list_size 0 \
    -hls_flags independent_segments+program_date_time+append_list \
    -hls_segment_filename '/srv/dvr/seg_%05d.ts' \
    /srv/dvr/dvr.m3u8
```

**RPi 5 (SW libx264 — HW H.264 encoder removed in BCM2712)**
```bash
libcamera-vid -t 0 --width 1920 --height 1080 --framerate 30 --codec yuv420 -o - | \
  ffmpeg -f rawvideo -pix_fmt yuv420p -s 1920x1080 -framerate 30 -i - \
    -c:v libx264 -preset ultrafast -tune zerolatency -g 60 -b:v 3000000 \
    -an \
    -f hls -hls_time 2 -hls_list_size 0 \
    -hls_flags independent_segments+program_date_time+append_list \
    -hls_segment_filename '/srv/dvr/seg_%05d.ts' \
    /srv/dvr/dvr.m3u8
```

> RPi 5 needs an active cooler for sustained 1080p30 SW encoding.

### 4.2 DVR-HLS muxer flags (key)

| Flag | Meaning |
|---|---|
| `-hls_time 2` | Segment duration. Shorter → lower latency, more files |
| `-hls_list_size 0` | Keep all segments in playlist (DVR window) |
| `-hls_flags independent_segments` | Each segment starts at keyframe — clean seeking |
| `-hls_flags program_date_time` | Absolute wall-clock tags |
| `-hls_flags append_list` | Survive ffmpeg restart by appending |
| `-hls_flags delete_segments` | **Avoid** — shrinks DVR window. Use cron-based cleanup instead |

### 4.3 LL-HLS (low-latency, RPi 5 recommended)
```
-hls_segment_type fmp4
-hls_fmp4_init_filename init.mp4
-hls_playlist_type event
```
LL-HLS reduces live latency from ~6–10 s (standard) to **~2 s**. Supported by iOS Safari 14+ and hls.js 1.x.

### 4.4 Thumbnails (hover preview)

```bash
ffmpeg -i /srv/dvr/dvr.m3u8 -vf "fps=1/10,scale=160:90" \
  -q:v 5 /srv/dvr/thumbs/raw_%06d.jpg

montage /srv/dvr/thumbs/raw_*.jpg -tile 10x10 -geometry 160x90 \
  /srv/dvr/thumbs/sprite_%04d.jpg
```

`thumbs.vtt`:
```
WEBVTT

00:00:00.000 --> 00:00:10.000
sprite_0001.jpg#xywh=0,0,160,90

00:00:10.000 --> 00:00:20.000
sprite_0001.jpg#xywh=160,0,160,90
...
```

### 4.5 nginx
```nginx
server {
  listen 8090;
  root /srv/dvr;

  location / {
    add_header Cache-Control no-cache;
    add_header Access-Control-Allow-Origin *;
    types {
      application/vnd.apple.mpegurl m3u8;
      video/mp2t                    ts;
      text/vtt                      vtt;
    }
  }
  location /player/ { alias /srv/dvr/player/; }
}
```

### 4.6 Phone player (hls.js + Plyr)
```html
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css">
</head>
<body style="margin:0;background:#000">
  <video id="player" controls crossorigin playsinline></video>
  <script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
  <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
  <script>
    const video = document.getElementById('player');
    const hls = new Hls({
      liveSyncDuration: 4,
      liveMaxLatencyDuration: 10,
      lowLatencyMode: true,
      backBufferLength: 60 * 60 * 4
    });
    hls.loadSource('/dvr.m3u8');
    hls.attachMedia(video);

    const player = new Plyr(video, {
      controls: ['play','progress','current-time','mute','volume','settings','pip','fullscreen'],
      previewThumbnails: { enabled: true, src: '/thumbs/thumbs.vtt' }
    });

    const liveBtn = document.createElement('button');
    liveBtn.textContent = '🔴 LIVE';
    liveBtn.onclick = () => { video.currentTime = hls.liveSyncPosition; };
    document.body.appendChild(liveBtn);
  </script>
</body>
</html>
```

---

## 5. Storage policy (SD card)

### 5.1 Capacity table

| Resolution / bitrate | 1 h | 4 h | 24 h | 7 days |
|---|---|---|---|---|
| 720p / 1.0 Mbps | 0.45 GB | 1.8 GB | 11 GB | 76 GB |
| 720p / 1.5 Mbps | 0.68 GB | 2.7 GB | 16 GB | 113 GB |
| 1080p / 2.0 Mbps | 0.9 GB | 3.6 GB | 22 GB | 151 GB |
| 1080p / 3.0 Mbps | 1.35 GB | 5.4 GB | 32 GB | 226 GB |

Thumbnails add ~5%.

### 5.2 Layout
```
/srv/dvr/
├── dvr.m3u8
├── seg_*.ts
├── thumbs/
│   ├── sprite_*.jpg
│   └── thumbs.vtt
└── player/index.html
```

### 5.3 Cleanup cron (4 h retention example)
```
*/10 * * * * pi /usr/local/bin/dvr-cleanup.sh
```
```bash
#!/bin/bash
RETAIN_HOURS=4
DVR_DIR=/srv/dvr
find $DVR_DIR -name 'seg_*.ts' -mmin +$((RETAIN_HOURS * 60)) -delete
find $DVR_DIR/thumbs -name 'sprite_*.jpg' -mmin +$((RETAIN_HOURS * 60 + 30)) -delete
python3 /usr/local/bin/trim_m3u8.py $DVR_DIR/dvr.m3u8 $RETAIN_HOURS
```

### 5.4 SD endurance
- Use **High-Endurance microSD** (SanDisk MAX Endurance, Samsung PRO Endurance).
- Standard cards (~10 TBW) ≈ 3 yrs at 1 Mbps 24/7.
- High-endurance (100–200 TBW) ≈ 30–60 yrs.
- USB SSD or NVMe HAT (RPi 5) eliminates wear concerns.

---

## 6. Per-board applicability

| Board | DVR feasibility |
|---|---|
| RPi 3B | 720p / 1 Mbps, 4 h retention practical |
| RPi 5 | 1080p / 3 Mbps, 24 h+ retention — sweet spot |
| Jetson Orin Nano | Strong HW encoder, can also add AI event markers |
| Jetson Nano | 1.9 GB RAM tight, 720p only |
| Zybo (PetaLinux) | Needs ffmpeg build, low priority |

Phase 1 = RPi 3B / 720p / 4 h. Promote to RPi 5 when satisfied.

---

## 7. Open decisions

- [ ] Board: start on RPi 3B vs wait for RPi 5
- [ ] Retention: 1 h / 4 h / 24 h / since-broadcast-start
- [ ] Recording trigger: ① always-on while booted / ② phone "Start broadcast" button
- [ ] Player: hls.js + Plyr / video.js / Shaka
- [ ] LL-HLS: yes (RPi 5) / standard HLS (RPi 3B)
- [ ] Storage: SD only / SD + USB SSD
- [ ] Auth: Tailscale only / explicit token

---

## 8. Roadmap

### Phase 1 — MVP (RPi 3B, 1–2 days)
- [ ] `/srv/dvr/` + perms
- [ ] systemd unit `camera-dvr.service` (libcamera-vid → ffmpeg HLS)
- [ ] nginx :8090 + static page
- [ ] phone via Tailscale → seek works
- Done = phone can play 1 h ago + LIVE button works

### Phase 2 — Thumbnail hover
- [ ] thumbnail extraction cron
- [ ] sprite generation (montage)
- [ ] thumbs.vtt generator (Python)
- Done = hover shows preview image

### Phase 3 — Retention + cleanup
- [ ] `dvr-cleanup.sh` + `trim_m3u8.py`
- [ ] cron registered
- [ ] SD usage monitored
- Done = old segments pruned, SD usage stable

### Phase 4 — UX polish
- [ ] LIVE badge + edge indicator
- [ ] Absolute clock display (programDateTime)
- [ ] PWA manifest + home icon
- [ ] (optional) auth layer
- Done = 1:1 with Chzzk UX

### Phase 5 — (optional) AI event markers
- [ ] External AI source (e.g. Jetson Orin YOLOv8) → webhook to RPi DVR
- [ ] Markers on seek bar
- [ ] "Events only" filter

### Phase 6 — (optional) RPi 5 migration
- [ ] 1080p30 LL-HLS
- [ ] NVMe HAT + 1 TB SSD
- [ ] Dual IMX219 (CSI x2)

---

## 9. Standards & tools — reference URLs

### Protocol standards
- **RFC 8216** — HTTP Live Streaming (IETF)
  https://datatracker.ietf.org/doc/html/rfc8216
- **Apple HLS portal**
  https://developer.apple.com/streaming/
- **Apple Low-Latency HLS**
  https://developer.apple.com/documentation/http-live-streaming/enabling-low-latency-http-live-streaming-hls
- **WebVTT (W3C)** — thumbnail tracks
  https://www.w3.org/TR/webvtt1/
- **MPEG-DASH** — ISO/IEC 23009-1 (alternative reference)

### Tools
- **ffmpeg HLS muxer** — https://ffmpeg.org/ffmpeg-formats.html#hls-2
- **libcamera** — https://libcamera.org/
- **hls.js** — https://github.com/video-dev/hls.js
- **Plyr** — https://github.com/sampotts/plyr
- **video.js** — https://github.com/videojs/video.js
- **Shaka Player** — https://github.com/shaka-project/shaka-player
- **MediaMTX** — https://github.com/bluenviron/mediamtx
- **nginx-rtmp-module** — https://github.com/arut/nginx-rtmp-module

### Practical guides
- Mux engineering blog — https://www.mux.com/blog
- Wowza HLS DVR knowledge base
- Raspberry Pi camera + ffmpeg threads on raspberrypi.stackexchange.com

---

## 10. Related papers

> URLs change; titles + venue + authors given for stable lookup via Google Scholar / DOI.

### HTTP adaptive streaming surveys
- Bentaleb, A., et al. "A Survey on Bitrate Adaptation Schemes for Streaming Media Over HTTP." *IEEE Communications Surveys & Tutorials*, 21(1), 2019.
- Sodagar, I. "The MPEG-DASH Standard for Multimedia Streaming Over the Internet." *IEEE MultiMedia*, 2011.
- Stockhammer, T. "Dynamic Adaptive Streaming over HTTP — Standards and Design Principles." *ACM MMSys 2011*.

### Low-latency streaming
- Bentaleb, A., Akcay, M.N., Lim, M., et al. "Common Media Client Data (CMCD) and Low-Latency CMAF Streaming." *IEEE Multimedia*, 2022.
- Apple WWDC 2020 — Session 10229 "What's new in HTTP Live Streaming"
  https://developer.apple.com/videos/play/wwdc2020/10229/

### DVR / time-shift
- Lederer, S., Müller, C., Timmerer, C. "Dynamic Adaptive Streaming over HTTP Dataset." *ACM MMSys 2012*.
- Begen, A.C., et al. "Watching Video over the Web: Part 1 — Streaming Protocols." *IEEE Internet Computing*, 2011.

### Edge video / IP cameras
- Ananthanarayanan, G., et al. "Real-time Video Analytics: The Killer App for Edge Computing." *IEEE Computer*, 2017.
- Hung, C., et al. "VideoEdge: Processing Camera Streams using Hierarchical Clusters." *IEEE/ACM SEC 2018*.

### Korean engineering blogs (search keywords)
- NAVER D2 — "라이브 스트리밍"
- Kakao tech blog — "라이브 방송 / HLS"
- Woowahan tech — "라이브 방송 도입기"

---

## 11. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| SD wear-out | card death, footage lost | High-Endurance microSD; USB SSD optional |
| RPi 3B thermal | encoder throttle | heatsink + small fan; cap at 720p |
| RPi 5 SW H.264 load | CPU saturation | active cooler; `-preset ultrafast` |
| LL-HLS Safari edge cases | phone won't play | auto-fallback to plain HLS |
| Tailscale bandwidth on cellular | drops/buffer | ≤1 Mbps; consider ABR ladder |
| NTP drift | bad `program_date_time` | systemd-timesyncd / chrony |
| Power loss → broken segment | last `.ts` corrupt | `append_list` recovers on restart |

---

## 12. Next action

1. **[Decide]** RPi 3B now vs wait for RPi 5
2. Then: provision `/srv/dvr/`, write systemd unit, nginx config, static player page in one pass
3. Phone via Tailscale → confirm seek works → proceed to Phase 2

---

## 13. Changelog

| Date | Note |
|---|---|
| 2026-05-02 | Initial draft (skeleton + references + roadmap) |
