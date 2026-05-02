# RPi Camera DVR — 구현 계획

> 작성일: 2026-05-02
> 목표: 라즈베리파이 IP카메라(IMX219 / Pi Camera Module)에 **치지직 / 트위치 / 유튜브 라이브 수준의 DVR(타임머신)** 재생 기능 추가
> 저장: SD카드 (옵션: USB SSD / RPi 5의 NVMe HAT)

---

## 1. 개요

### 1.1 한 줄 요약
휴대폰으로 RPi 카메라 라이브를 보다가 시크바를 왼쪽으로 끌면 **방송 시작 시점(또는 최근 N시간)** 까지 되돌려 볼 수 있고, 호버 시 **썸네일 미리보기**, "실시간" 버튼으로 라이브 복귀 — 치지직과 동일한 UX를 라즈베리파이 한 대로 구현.

### 1.2 왜 만드는가
기존 단일 스트림 Pi 구성(libcamera-vid → MJPEG / RTSP)은 **라이브 only**. 과거 영상 회수 불가. DVR 레이어를 얹어 "블랙박스 + 라이브" 일체형 카메라로 만들기 위함.

---

## 2. 목표 UX (치지직 레퍼런스)

| 요소 | 동작 |
|---|---|
| 빨간 **LIVE** 배지 | 재생 위치가 `liveSyncPosition`과 일치할 때 표시 |
| **시크바를 끝까지 왼쪽으로** | 방송 시작 시점 또는 보존 시간 한계로 점프 |
| **호버 미리보기** | 커서 위치에 해당 시점의 WebVTT 썸네일 팝업 |
| **"실시간" 버튼** | `video.currentTime = hls.liveSyncPosition` |
| 일시정지 / 배속 / 풀스크린 | 표준 비디오 컨트롤 |
| 시간 오프셋 표시 | `-06:48` 식의 라이브 대비 캡션 |

---

## 3. 시스템 아키텍처

```
[IMX219 카메라]
       │
       ▼ MIPI CSI
[RPi 3B 또는 RPi 5]
  ├── libcamera-vid / ffmpeg  (H.264 인코딩)
  ├── ffmpeg HLS muxer
  │     ├── dvr.m3u8           (DVR 전체 플레이리스트)
  │     ├── seg_00001.ts ...   (2초 세그먼트, SD에 누적)
  │     └── thumbs/
  │           ├── sprite_0001.jpg (10×10 = 100썸네일/장)
  │           └── thumbs.vtt
  ├── 정리 cron                (보존 시간 초과분 삭제)
  └── nginx (정적 서빙, :8090)
       │
       ▼ Tailscale (또는 LAN)
[휴대폰 브라우저]
  ├── hls.js + Plyr
  ├── LIVE 버튼 / 시크바 / VTT 썸네일 호버
  └── (선택) PWA 설치
```

---

## 4. 컴포넌트 상세

### 4.1 캡처 + H.264 인코딩

**RPi 3B (HW 인코더 — VideoCore IV)**
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

**RPi 5 (SW libx264 — BCM2712에서 HW H.264 인코더 제거됨)**
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

> RPi 5에서 1080p30 SW 인코딩을 지속하려면 **액티브 쿨러 필수**.

### 4.2 DVR-HLS muxer 핵심 옵션

| 옵션 | 의미 |
|---|---|
| `-hls_time 2` | 세그먼트 길이 (작을수록 라이브 지연↓, 파일 수↑) |
| `-hls_list_size 0` | 모든 세그먼트를 플레이리스트에 유지 (= DVR 윈도우) |
| `-hls_flags independent_segments` | 각 세그먼트가 키프레임으로 시작 → 시크 정확도↑ |
| `-hls_flags program_date_time` | 절대 시각 태그 부여 |
| `-hls_flags append_list` | ffmpeg 재시작 시 기존 m3u8에 이어 붙임 |
| `-hls_flags delete_segments` | **사용 X** — DVR 윈도우가 줄어듦. cron 기반 정리 권장 |

### 4.3 LL-HLS (저지연, RPi 5 권장)
```
-hls_segment_type fmp4
-hls_fmp4_init_filename init.mp4
-hls_playlist_type event
```
LL-HLS 적용 시 라이브 지연이 **~6–10초(표준) → ~2초** 로 단축. iOS Safari 14+, hls.js 1.x 지원.

### 4.4 썸네일 (호버 미리보기)

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

### 4.6 휴대폰 플레이어 (hls.js + Plyr)
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
    liveBtn.textContent = '🔴 실시간';
    liveBtn.onclick = () => { video.currentTime = hls.liveSyncPosition; };
    document.body.appendChild(liveBtn);
  </script>
</body>
</html>
```

---

## 5. 저장 정책 (SD카드)

### 5.1 용량 계산

| 해상도 / 비트레이트 | 1시간 | 4시간 | 24시간 | 7일 |
|---|---|---|---|---|
| 720p / 1.0 Mbps | 0.45 GB | 1.8 GB | 11 GB | 76 GB |
| 720p / 1.5 Mbps | 0.68 GB | 2.7 GB | 16 GB | 113 GB |
| 1080p / 2.0 Mbps | 0.9 GB | 3.6 GB | 22 GB | 151 GB |
| 1080p / 3.0 Mbps | 1.35 GB | 5.4 GB | 32 GB | 226 GB |

썸네일은 약 +5%.

### 5.2 디렉토리 구조
```
/srv/dvr/
├── dvr.m3u8
├── seg_*.ts
├── thumbs/
│   ├── sprite_*.jpg
│   └── thumbs.vtt
└── player/index.html
```

### 5.3 정리 cron (보존 4시간 예시)
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

### 5.4 SD카드 수명
- **High-Endurance microSD 필수** (SanDisk MAX Endurance, Samsung PRO Endurance).
- 일반 카드(약 10 TBW) → 1Mbps 24/7 운용 시 약 3년.
- 고내구 카드(100~200 TBW) → 약 30~60년.
- USB SSD 또는 NVMe HAT(RPi 5) 사용 시 마모 우려 사실상 제거.

---

## 6. 보드별 적용 가능성

| 보드 | DVR 적용 |
|---|---|
| RPi 3B | 720p / 1Mbps · 4시간 보존이 현실선 |
| RPi 5 | 1080p / 3Mbps · 24시간+ 보존 — sweet spot |
| Jetson Orin Nano | HW 인코더 강력, AI 이벤트 마커까지 추가 가능 |
| Jetson Nano | RAM 1.9GB라 빠듯, 720p로만 |
| Zybo (PetaLinux) | ffmpeg 빌드 필요, 우선순위 낮음 |

Phase 1은 **RPi 3B / 720p / 4시간**으로 검증 → 만족하면 RPi 5로 확장.

---

## 7. 결정해야 할 사항

- [ ] 보드: RPi 3B로 시작 vs RPi 5 도착 대기
- [ ] 보존 시간: 1시간 / 4시간 / 24시간 / 방송 시작부터 누적
- [ ] 녹화 트리거: ① 부팅 후 항상 녹화 / ② 휴대폰의 "방송 시작" 버튼
- [ ] 플레이어: hls.js + Plyr / video.js / Shaka
- [ ] LL-HLS 적용 여부 (RPi 5 yes / RPi 3B 표준 HLS)
- [ ] 저장 매체: SD only / SD + USB SSD
- [ ] 인증: Tailscale only / 별도 토큰

---

## 8. 단계별 로드맵

### Phase 1 — MVP (RPi 3B, 1~2일)
- [ ] `/srv/dvr/` 디렉토리 + 권한
- [ ] systemd 유닛 `camera-dvr.service` (libcamera-vid → ffmpeg HLS)
- [ ] nginx :8090 + 정적 페이지
- [ ] 휴대폰에서 Tailscale 경유 시크 동작 확인
- 완료 기준 = 휴대폰에서 1시간 전 영상 재생 + "실시간" 버튼 동작

### Phase 2 — 썸네일 호버
- [ ] ffmpeg 썸네일 추출 cron
- [ ] montage 스프라이트 합성
- [ ] thumbs.vtt 자동 생성 스크립트 (Python)
- 완료 기준 = 호버 시 미리보기 표시

### Phase 3 — 보존 정책 + 정리
- [ ] `dvr-cleanup.sh` + `trim_m3u8.py`
- [ ] cron 등록
- [ ] SD 사용량 모니터링
- 완료 기준 = 보존 시간 초과분 자동 삭제, SD 사용량 안정

### Phase 4 — UX 마감
- [ ] LIVE 배지 + 라이브 위치 indicator
- [ ] 절대 시각 표시 (programDateTime)
- [ ] PWA manifest + 홈 아이콘
- [ ] (선택) 인증 레이어
- 완료 기준 = 치지직 UX와 1:1 매칭

### Phase 5 — (선택) AI 이벤트 마커
- [ ] 외부 AI 소스(예: Jetson Orin YOLOv8) → webhook 으로 RPi DVR에 전송
- [ ] 시크바에 마커 표시
- [ ] "이벤트 클립만 보기" 필터

### Phase 6 — (선택) RPi 5 마이그레이션
- [ ] 1080p30 LL-HLS
- [ ] NVMe HAT + 1TB SSD
- [ ] 듀얼 IMX219 (CSI 2포트)

---

## 9. 표준 문서 / 도구 — 레퍼런스 URL

### 프로토콜 표준
- **RFC 8216** — HTTP Live Streaming (IETF)
  https://datatracker.ietf.org/doc/html/rfc8216
- **Apple HLS 포털**
  https://developer.apple.com/streaming/
- **Apple Low-Latency HLS**
  https://developer.apple.com/documentation/http-live-streaming/enabling-low-latency-http-live-streaming-hls
- **WebVTT (W3C)** — 썸네일 트랙 표준
  https://www.w3.org/TR/webvtt1/
- **MPEG-DASH** — ISO/IEC 23009-1 (대안 참고)

### 도구
- **ffmpeg HLS muxer** — https://ffmpeg.org/ffmpeg-formats.html#hls-2
- **libcamera** — https://libcamera.org/
- **hls.js** — https://github.com/video-dev/hls.js
- **Plyr** — https://github.com/sampotts/plyr
- **video.js** — https://github.com/videojs/video.js
- **Shaka Player** — https://github.com/shaka-project/shaka-player
- **MediaMTX** — https://github.com/bluenviron/mediamtx
- **nginx-rtmp-module** — https://github.com/arut/nginx-rtmp-module

### 실용 가이드
- Mux 엔지니어링 블로그 — https://www.mux.com/blog
- Wowza HLS DVR 지식 베이스
- raspberrypi.stackexchange.com 의 Pi 카메라 + ffmpeg 사례 글

---

## 10. 관련 논문

> URL은 자주 바뀌므로 **제목 + 저자 + 학회/저널** 로 표기. Google Scholar / DOI 검색 권장.

### HTTP Adaptive Streaming 서베이
- Bentaleb, A., et al. "A Survey on Bitrate Adaptation Schemes for Streaming Media Over HTTP." *IEEE Communications Surveys & Tutorials*, 21(1), 2019.
- Sodagar, I. "The MPEG-DASH Standard for Multimedia Streaming Over the Internet." *IEEE MultiMedia*, 2011.
- Stockhammer, T. "Dynamic Adaptive Streaming over HTTP — Standards and Design Principles." *ACM MMSys 2011*.

### 저지연 스트리밍
- Bentaleb, A., Akcay, M.N., Lim, M., et al. "Common Media Client Data (CMCD) and Low-Latency CMAF Streaming." *IEEE Multimedia*, 2022.
- Apple WWDC 2020 — Session 10229 "What's new in HTTP Live Streaming"
  https://developer.apple.com/videos/play/wwdc2020/10229/

### DVR / 타임시프트
- Lederer, S., Müller, C., Timmerer, C. "Dynamic Adaptive Streaming over HTTP Dataset." *ACM MMSys 2012*.
- Begen, A.C., et al. "Watching Video over the Web: Part 1 — Streaming Protocols." *IEEE Internet Computing*, 2011.

### 엣지 비디오 / IP카메라
- Ananthanarayanan, G., et al. "Real-time Video Analytics: The Killer App for Edge Computing." *IEEE Computer*, 2017.
- Hung, C., et al. "VideoEdge: Processing Camera Streams using Hierarchical Clusters." *IEEE/ACM SEC 2018*.

### 한국어 엔지니어링 블로그 (검색 키워드)
- NAVER D2 — "라이브 스트리밍"
- Kakao tech blog — "라이브 방송 / HLS"
- 우아한형제들 기술블로그 — "라이브 방송 도입기"

---

## 11. 위험 요소와 완화

| 리스크 | 영향 | 완화책 |
|---|---|---|
| SD카드 마모 | 카드 사망, 영상 손실 | High-Endurance microSD, USB SSD 옵션 |
| RPi 3B 발열 | 인코더 throttle | 방열판 + 작은 팬, 720p로 제한 |
| RPi 5 SW H.264 부하 | CPU saturation | 액티브 쿨러, `-preset ultrafast` |
| LL-HLS Safari 호환 이슈 | 폰에서 안 열림 | 일반 HLS fallback 자동 협상 |
| Tailscale LTE/5G 대역폭 | 끊김/버퍼링 | ≤1 Mbps, ABR 멀티 트랙 고려 |
| NTP 시각 어긋남 | `program_date_time` 신뢰성↓ | systemd-timesyncd / chrony |
| 정전 → 세그먼트 깨짐 | 마지막 .ts 손상 | `append_list` 로 재시작 시 복구 |

---

## 12. 다음 액션

1. **[결정]** RPi 3B로 즉시 시작 vs RPi 5 도착 대기
2. 결정되면 `/srv/dvr/` 셋업 + systemd 유닛 + nginx + 정적 플레이어 페이지 한 번에 작성
3. 휴대폰 Tailscale 접속 → 시크 동작 확인 → Phase 2 진행

---

## 13. 변경 이력

| 일자 | 내용 |
|---|---|
| 2026-05-02 | 최초 작성 (영문) |
| 2026-05-02 | 한글 번역으로 교체 |
