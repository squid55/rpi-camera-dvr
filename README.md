# rpi-camera-dvr

라즈베리파이 IP카메라(IMX219 / Pi Camera Module)에 **치지직 / 트위치 / 유튜브 라이브 수준의 DVR(타임머신) 재생 + 무지연(WebRTC) 라이브**를 결합한 IP카메라 노드.

휴대폰으로 라이브를 보다가 시크바를 왼쪽으로 끌면 **방송 시작 시점(또는 최근 N시간)** 까지 되돌려 볼 수 있고, "**실시간**" 버튼 한 번이면 라이브로 복귀 — 즉 치지직과 동일한 UX를 라즈베리파이 한 대 + SD카드 저장으로 구현.

라이브는 [WebRTC (RFC 8825)](https://datatracker.ietf.org/doc/html/rfc8825) 패킷 기반으로 ~0.2초, 시크백은 [HTTP Live Streaming (RFC 8216)](https://datatracker.ietf.org/doc/html/rfc8216) 위에 [`EXT-X-PLAYLIST-TYPE:EVENT`](https://datatracker.ietf.org/doc/html/rfc8216#section-4.3.3.5) timeline으로 4시간 누적.

---

## Table of Contents

1. [System architecture](#1-system-architecture)
2. [Tech stack](#2-tech-stack)
3. [Engineering decisions (8 ADRs)](#3-engineering-decisions-8-adrs)
4. [Performance & resource budget](#4-performance--resource-budget)
5. [Repository layout](#5-repository-layout)
6. [Quick install](#6-quick-install)
7. [Usage](#7-usage)
8. [Operations](#8-operations)
9. [Documentation map](#9-documentation-map)
10. [Roadmap & status](#10-roadmap--status)
11. [Risk register](#11-risk-register)
12. [Related projects & OSS NVR comparison](#12-related-projects--oss-nvr-comparison)
13. [License & contributing](#13-license--contributing)

---

## 1. System architecture

```
[IMX219 카메라]
       │ MIPI CSI-2 (Sony 8MP, 1280x720@15)
       ▼
[Raspberry Pi 3B (Debian 13 Trixie aarch64)]
  │
  ├── rpicam-vid                                   ─── HW 인코더 (bcm2835-codec, v4l2m2m)
  │     --codec h264 --profile baseline --inline   ─── 매 keyframe SPS/PPS 인라인 (HLS 호환)
  │     --intra 30 --bitrate 1000000               ─── 2초 GOP @ 15fps, 1Mbps CBR
  │       │ stdout = annex-B H.264 elementary stream
  │       ▼ pipe
  ├── ffmpeg (-c:v copy, 재인코딩 0)
  │     ├──► HLS muxer
  │     │     -hls_time 2 -hls_list_size 0
  │     │     -hls_playlist_type event             ─── m3u8 전체를 seekable timeline으로 광고
  │     │     -hls_flags independent_segments
  │     │       +program_date_time+append_list     ─── 매 segment 절대시각 + restart 시 이어쓰기
  │     │     -strftime 1
  │     │     -hls_segment_filename
  │     │       seg_%Y%m%dT%H%M%S.ts               ─── 파일명에 wall-clock (restart 충돌 회피)
  │     │     /srv/dvr/dvr.m3u8 + seg_*.ts
  │     │
  │     └──► RTSP push (-f rtsp -rtsp_transport tcp)
  │           rtsp://localhost:8554/cam            ─── localhost only, MediaMTX로
  │
  ├── MediaMTX v1.18.1 (single binary daemon)
  │     :8554/TCP   RTSP ingest                    ─── ffmpeg가 publish
  │     :8889/TCP   WebRTC HTTP (WHEP)             ─── POST /cam/whep -> SDP answer
  │     :8189/UDP   ICE/SRTP                       ─── 미디어 전송
  │     webrtcAdditionalHosts: [<tailscale-ip>]    ─── ICE candidate 광고
  │
  ├── nginx :8090
  │     /dvr.m3u8, /seg_*.ts                       ─── 정적 파일 서빙 (Cache-Control: no-cache)
  │     /player/                                   ─── 단일 페이지 SPA (hls.js + Plyr + RTCPeerConnection)
  │
  └── cron (10분 주기) → /usr/local/bin/dvr-cleanup.sh
        find -mmin +240 -delete                    ─── 4h 보존
        trim_m3u8.py                               ─── 디스크와 m3u8 동기화
       │
       │ Tailscale 0.x.x.x (NAT 통과 P2P, mesh VPN)
       │ STUN/TURN 불필요 (Tailscale가 ICE 대체)
       ▼
[브라우저 (PC/모바일)]
  player/index.html
    ┌─ liveVideo  (WebRTC, RTCPeerConnection.ontrack → srcObject)
    │   ─ z-index: 3, pointer-events: none (오버레이)
    │   ─ controls 없음, dvrVideo의 컨트롤이 시계가 됨
    │
    └─ dvrVideo   (HLS, hls.js MSE → src)
        ─ controls 있음 (Plyr UI: progress, fullscreen 등)
        ─ 페이지 lifetime 동안 attach 영구 유지
        ─ 라이브 모드일 때도 백그라운드에서 라이브 끝쪽 추종

  토글 휴리스틱:
    - seeking event → 라이브 위치 ±3초 밖이면 enterSeekMode
      (liveVideo 숨김, dvrVideo가 그 위치로)
    - pause event → enterSeekMode (정지 화면)
    - "실시간으로" button → enterLiveMode
      (liveVideo 표시, dvrVideo.currentTime = liveSyncPosition)
    - suppressSeekOnce flag로 자기 자신이 트리거한 seek 1회 무시
```

자세한 설계 근거 — 컴포넌트별 책임 분담, dual-`<video>` 토글이 필요했던 이유, fan-out 설계 — 는 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 2. Tech stack

### 2.1 하드웨어

| 항목 | 모델 | 비고 |
|---|---|---|
| SBC | Raspberry Pi 3B (BCM2837, Cortex-A53 4코어 1.2GHz, 1GB LPDDR2) | aarch64 64-bit OS 사용 |
| 카메라 | Sony IMX219 8MP (Pi Camera v2 호환) | MIPI CSI-2 4-lane |
| 저장 | microSD 16GB | High-Endurance 권장 (TBW ↑) |
| 네트워크 | 내장 2.4GHz Wi-Fi 또는 100Mbps Ethernet | Tailscale direct P2P |

### 2.2 OS / runtime

| 항목 | 버전 | 용도 |
|---|---|---|
| Raspberry Pi OS Bookworm/Trixie 64-bit | Debian 13 (aarch64) | 베이스 OS |
| systemd | 256+ | 서비스 supervisor |
| systemd-timesyncd 또는 chrony | 활성 | NTP 동기 — `EXT-X-PROGRAM-DATE-TIME` 신뢰성 |
| Python | 3.12 (apt 기본) | `stream_server.py` supervisor + `trim_m3u8.py` |

### 2.3 미디어 파이프라인 (RPi 측)

| 도구 | 버전 | 라이선스 | 역할 |
|---|---|---|---|
| `rpicam-apps` (`rpicam-vid`) | apt 기본 | BSD-2 | libcamera 기반 카메라 캡처 + H.264 HW 인코딩 |
| libcamera | apt 기본 | LGPL-2.1 | 카메라 stack |
| H.264 HW 인코더 | bcm2835-codec (VideoCore IV) | — | profile=Baseline / level=4.0 |
| ffmpeg | 6.x apt | LGPL/GPL | demux + HLS mux + RTSP push (`-c:v copy`만, 재인코딩 0) |
| [MediaMTX](https://github.com/bluenviron/mediamtx) | v1.18.1 (linux_arm64 single binary) | MIT | RTSP ingest + WebRTC(WHEP) publish + RTP packetize |
| nginx | apt 기본 | BSD-2 | 정적 m3u8/.ts/플레이어 페이지 서빙 |

### 2.4 클라이언트 (브라우저)

| 라이브러리 | 버전 | 라이선스 | 용도 |
|---|---|---|---|
| [hls.js](https://github.com/video-dev/hls.js) | 1.x (CDN: jsDelivr) | Apache-2.0 | HLS m3u8/.ts 디코딩 + MSE 재생 |
| [Plyr](https://github.com/sampotts/plyr) | 3.7.8 (CDN) | MIT | 비디오 컨트롤 UI (progress / fullscreen / pip / settings) |
| `RTCPeerConnection` | 브라우저 native | — | WHEP 클라이언트 — POST SDP offer → answer 협상 후 RTP 수신 |
| `MediaSource Extensions` | 브라우저 native | — | hls.js의 video element 부착 backend |

### 2.5 프로토콜 표준

| 프로토콜 | 용도 | 표준 |
|---|---|---|
| HLS | DVR 시크백 | [RFC 8216](https://datatracker.ietf.org/doc/html/rfc8216) |
| HLS EVENT playlist | 시크 가능 timeline | [§4.3.3.5](https://datatracker.ietf.org/doc/html/rfc8216#section-4.3.3.5) |
| WebRTC | 라이브 0.2초 | [RFC 8825](https://datatracker.ietf.org/doc/html/rfc8825) overview |
| SRTP/RTP | WebRTC 미디어 | [RFC 3711](https://datatracker.ietf.org/doc/html/rfc3711), [RFC 3550](https://datatracker.ietf.org/doc/html/rfc3550) |
| WHEP | WebRTC HTTP egress (player 협상) | [IETF draft `whep`](https://datatracker.ietf.org/doc/draft-murillo-whep/) |
| RTSP | 내부 ffmpeg → MediaMTX publish | [RFC 7826](https://datatracker.ietf.org/doc/html/rfc7826) (RTSP 2.0) |
| ICE / STUN | WebRTC NAT 통과 | [RFC 8445](https://datatracker.ietf.org/doc/html/rfc8445) (Tailscale 환경에선 거의 불필요) |
| Annex-B / SPS/PPS | H.264 elementary stream framing | ITU-T H.264 |

### 2.6 포트 맵

| 포트 | 프로토콜 | 노출 | 용도 |
|---|---|---|---|
| 8090/TCP | HTTP (nginx) | LAN/Tailscale | 정적 m3u8/.ts/player |
| 8889/TCP | HTTP (MediaMTX) | LAN/Tailscale | WebRTC WHEP 시그널링 (`POST /cam/whep`) |
| 8189/UDP | SRTP/ICE (MediaMTX) | LAN/Tailscale | WebRTC 미디어 전송 |
| 8554/TCP | RTSP (MediaMTX) | **localhost only** | ffmpeg push 수신 |
| ~~8080/TCP~~ | ~~MJPEG~~ | — | **본 빌드에서 제거** ([ADR #8](#3-engineering-decisions-8-adrs)) |

---

## 3. Engineering decisions (8 ADRs)

이 시스템이 왜 지금의 모습이 됐는가. 각 결정에는 대안과 채택 사유, 그리고 (해당하면) 측정 데이터.

### ADR #1 — H.264 profile = Baseline

| | |
|---|---|
| **Context** | rpicam-vid HW 인코더는 Baseline / Main / High 셋 모두 지원. WebRTC 클라이언트는 [W3C Media Capabilities](https://w3c.github.io/media-capabilities/)에서 profile별 디코더 가용성 다름. |
| **Alternatives** | (a) High (효율 ~10% ↑, 더 나은 압축) (b) Main (B-frame 가능) (c) Baseline (I/P만, B-frame 없음) |
| **Decision** | **Baseline**. |
| **Rationale** | Chrome/Firefox/Safari 모두 Baseline은 native 디코드 OK. High는 일부 브라우저에서 `setRemoteDescription` 시 SDP answer가 비어 오거나 디코드 실패 → WebRTC HLS-fallback. |
| **Consequence** | 같은 화질 대비 비트레이트 +5~10% 필요. 1Mbps 720p15에선 체감 차이 미미. |
| **Verification** | `ffprobe -show_entries stream=profile seg_*.ts` → `Baseline`. 브라우저 콘솔에서 `pc.getStats()`의 `frames-decoded` 증가. |

### ADR #2 — GOP = 30 frames (= 2s @ 15fps)

| | |
|---|---|
| **Context** | HLS segment 시작은 키프레임이어야 시크 정확 ([RFC 8216 §3.4](https://datatracker.ietf.org/doc/html/rfc8216#section-3.4)). |
| **Decision** | `--intra 30` + `-hls_time 2` 정확히 일치. |
| **Rationale** | 시크 단위 = 2초. fragment-aligned. |
| **Consequence** | 비트레이트 효율 약간 ↓ (key frame 더 자주). |

### ADR #3 — H.264 inline SPS/PPS (rpicam-vid `--inline`)

| | |
|---|---|
| **Context** | `h264_v4l2m2m`은 SPS/PPS를 첫 packet에만 출력. ffmpeg HLS muxer는 매 segment에 inject 안 함. |
| **Alternatives** | (a) ffmpeg `-bsf:v dump_extra=freq=keyframe` (b) HLS fmp4 (init.mp4 + .m4s) (c) rpicam-vid `--inline` |
| **Decision** | **(c) `--inline`**. |
| **Rationale** | (a)는 v4l2m2m이 ffmpeg에 extradata 보고 안 해서 BSF가 dump할 게 없음 (실제 시도 → 실패). (b)는 hls.js 호환은 OK이지만 cleanup 스크립트 + cron 재작성 필요. (c)는 rpicam-vid가 매 keyframe에 NAL을 자동 inject — 한 줄 변경. |
| **Verification** | `ffprobe -v error seg_*.ts` 출력에 `non-existing PPS 0` 0건. (자세히는 [`docs/POST-MORTEM.md` §2](docs/POST-MORTEM.md#2-hls-세그먼트가-spspps-누락--검정-화면).) |

### ADR #4 — HLS playlist type = EVENT

| | |
|---|---|
| **Context** | hls.js는 m3u8 첫 fetch 시 `EXT-X-PLAYLIST-TYPE` / `EXT-X-ENDLIST` / 마지막 segment age 등으로 live/event/vod 분류. 분류가 잘못되면 backward seek 차단. |
| **Alternatives** | (a) 명시 없음 (default) (b) `VOD` (c) `EVENT` |
| **Decision** | **EVENT** (`-hls_playlist_type event`). |
| **Rationale** | (a)는 sliding-window live로 인식 → 시크 시 `liveSyncPosition`으로 강제 복귀. (b)는 `ENDLIST`가 박혀 라이브성 사라짐. (c)는 처음부터 끝까지 시크 가능 + 새 segment append 가능. |
| **Verification** | `grep PLAYLIST-TYPE /srv/dvr/dvr.m3u8` → `#EXT-X-PLAYLIST-TYPE:EVENT`. |

### ADR #5 — Frame rate / bitrate = 15fps / 1Mbps @ 720p

| | |
|---|---|
| **Context** | RPi 3B 4코어 Cortex-A53 1.2GHz는 720p30 SW 디코드/인코드를 풀로 돌리면 LOAD 6+. |
| **Alternatives** | (a) 720p30 1.5Mbps (b) 720p15 1Mbps (c) 1080p — 메모리 부족 |
| **Decision** | **(b) 720p15 1Mbps**. |
| **Rationale** | LOAD ~1.8 (4코어, 안정 영역). DVR 4시간 = 1.8GB. 카메라 모니터링 용도엔 15fps 충분. |
| **Verification** | `uptime` 1m 평균 < 4.0 (정원), 측정값 ~1.8. |

### ADR #6 — DVR 보존 = 4시간 (cron 외부 정리)

| | |
|---|---|
| **Context** | `-hls_list_size 0`은 sliding 안 함 → 무한 누적. 보존 정책이 별도 필요. |
| **Alternatives** | (a) ffmpeg `-hls_flags delete_segments` (b) cron + `find -mmin +N -delete` + m3u8 trim |
| **Decision** | **(b)**. |
| **Rationale** | (a)는 ffmpeg가 직접 지우면 m3u8에서도 즉시 빠져 시크 가능 윈도우가 줄어듦. (b)는 segment 파일 보존과 m3u8 등재를 분리 가능. cron 10분 주기 + `trim_m3u8.py`. |
| **Verification** | `ls /srv/dvr/seg_*.ts | wc -l` ~7200 (= 4h × 30 segments/min). |

### ADR #7 — Authentication = Tailscale only

| | |
|---|---|
| **Context** | RPi가 외부에 공개되면 누구나 영상 시청 가능. |
| **Alternatives** | (a) nginx `auth_basic` (b) JWT/OAuth (c) Tailscale ACL |
| **Decision** | **(c)**. |
| **Rationale** | Tailscale가 이미 mesh VPN — RPi에 도달하려면 ACL 통과 필요. nginx/MediaMTX 자체는 인증 없이 운영 가능 → 코드 단순. |
| **Trade-off** | Tailscale 미가입 단말 접근 불가. 외부 공개가 필요하면 (a)/(b) 추가 가능 (nginx `auth_basic` snippet은 [`docs/TROUBLESHOOTING.md` Q&A](docs/TROUBLESHOOTING.md)). |

### ADR #8 — MJPEG 8080 출력 제거

| | |
|---|---|
| **Context** | 멀티보드 뷰어 호환을 위해 8080에 multipart/x-mixed-replace MJPEG도 같이 송출 시도. 그러나 ffmpeg 입력이 H.264이라 MJPEG 출력 시 SW 디코드 + SW MJPEG 인코드 발생. |
| **Measurement** | LOAD 1m avg = **7.8** (4코어 정원 초과, SSH 응답성 저하 관측). |
| **Alternatives** | (a) MJPEG 출력 다운그레이드 (480x270/8fps) — LOAD ~6 정도 (b) MJPEG 제거 — LOAD 1.8 |
| **Decision** | **(b) 제거**. WebRTC가 라이브 담당. |
| **Trade-off** | 멀티보드 뷰어(`localhost:9090`)의 RPi 3B 패널은 connection refused → 검정. 사용자는 DVR 페이지(`8090/player/`)에서 라이브 + 시크 모두 사용. |

전체 사건 흐름은 [`docs/POST-MORTEM.md`](docs/POST-MORTEM.md).

---

## 4. Performance & resource budget

### 4.1 측정 환경

- 보드: Raspberry Pi 3B, BCM2837, 1GB RAM
- OS: Debian 13 Trixie aarch64, kernel 6.x
- 카메라: IMX219 (Pi Camera v2)
- 저장: 16GB Class 10 SD (TBW ~10TB)
- 네트워크: Wi-Fi 2.4GHz, Tailscale direct
- 측정 시점: 2026-05-02 ~ 2026-05-03, 운영 중 안정 상태

### 4.2 측정값

| 항목 | 측정 | 정원/한계 | 마진 |
|---|---|---|---|
| LOAD (1m avg) | **1.8** | 4.0 (4코어 = 100%) | 55% 여유 |
| LOAD (15m avg) | 1.5 | 4.0 | 62% 여유 |
| RAM | **470 MB** / 906 MB | OOM 직전 ~850 | OK |
| RPi → 클라이언트 대역 | ~2 Mbps (HLS+WebRTC 동시) | 100 Mbps | 충분 |
| HLS segment 생성 | 30 segments/min × ~250KB | — | — |
| 4h DVR 디스크 | **1.8 GB** | 9.7 GB free | 21% 사용 |
| 라이브 지연 (WebRTC) | **~0.2초** | — | — |
| 라이브 지연 (HLS fallback) | ~3초 | 6초(권장) | OK |
| 동시 클라이언트 | 5명 검증, 이론상 10+명 | nginx 정적 ∞ + WebRTC N stream | — |

### 4.3 측정 명령어

```bash
# 1. 시스템 부하
uptime                                          # 1m / 5m / 15m
top -bn1 | grep -E "ffmpeg|rpicam|mediamtx"     # 컴포넌트별 CPU%

# 2. 메모리
free -h
ps -o pid,pcpu,pmem,comm -p $(pgrep -f stream_server.py)

# 3. HLS segment 페이스
watch -n 5 'ls /srv/dvr/seg_*.ts | wc -l'      # 분당 ~30 증가가 정상

# 4. 라이브 지연 (실측)
# 폰 화면에 시계 띄우고 카메라로 그 시계를 비춤. 화면-원본 차이를 슬로모션 캡처

# 5. 클라이언트 대역
# 브라우저 DevTools Network 탭, .ts 평균 ~125 KB/s + WebRTC ~125 KB/s

# 6. WebRTC 실측 stats
# 브라우저 콘솔: pc.getStats().then(s => [...s.values()].forEach(v => v.type==='inbound-rtp' && console.log(v)))
#   - framesDecoded, framesDropped, jitter, packetsLost
```

---

## 5. Repository layout

```
.
├── README.md                    ← 본 문서
├── LICENSE                      ← MIT
├── .gitignore
│
├── src/
│   └── stream_server.py         ← rpicam-vid + ffmpeg supervisor
│                                  (systemd unit ExecStart 대상)
├── config/
│   ├── mediamtx.yml             ← MediaMTX 설정 (RTSP + WebRTC)
│   └── nginx-dvr.conf           ← :8090 nginx site
│
├── systemd/
│   ├── camera-stream.service    ← stream_server.py supervisor
│   └── mediamtx.service         ← MediaMTX 데몬
│
├── scripts/
│   ├── dvr-cleanup.sh           ← 4h 보존 정책 (find -mmin +240 -delete)
│   ├── trim_m3u8.py             ← 디스크와 m3u8 동기화
│   └── dvr-cleanup.cron         ← /etc/cron.d 등록용
│
├── web/
│   ├── player/
│   │   └── index.html           ← dual-<video> 토글 SPA
│   └── thumbs/
│       └── thumbs.vtt           ← Phase 2 placeholder (WebVTT 빈 파일)
│
└── docs/
    ├── ARCHITECTURE.md          ← 데이터 흐름, 컴포넌트별 책임
    ├── STACK.md                 ← 버전 표 + 라이선스
    ├── INSTALL.md               ← as-built 기준 설치 단계
    ├── SETUP-GUIDE.md           ← OS 굽기부터의 14단계 매뉴얼
    ├── CONCEPTS.md              ← HLS / DVR / LL-HLS / WebVTT 개념
    ├── HARDWARE.md              ← 보드/카메라/SD/SSD/케이스 비교
    ├── IMPLEMENTATION-PLAN.md   ← 6단계 로드맵 + ffmpeg 옵션 상세
    ├── TROUBLESHOOTING.md       ← 카탈로그형 가이드 (11 섹션)
    ├── POST-MORTEM.md           ← 본 빌드 6 incidents (post-mortem)
    └── REFERENCES.md            ← RFC/W3C/Apple + OSS NVR + 학술 12편
```

---

## 6. Quick install

전제: Raspberry Pi OS Trixie 64-bit, IMX219 CSI 결선됨, Tailscale 가입됨.

### 6.1 의존성

```bash
sudo apt update
sudo apt install -y ffmpeg nginx rpicam-apps libcamera-tools

# 검증
rpicam-vid --help | head -2                                      # libcamera 인식
ffmpeg -encoders 2>/dev/null | grep -E "h264|mjpeg" | head -3
v4l2-ctl --list-devices | grep -A1 unicam                        # CSI sensor 인식
```

### 6.2 MediaMTX

```bash
cd /tmp
URL="https://github.com/bluenviron/mediamtx/releases/download/v1.18.1/mediamtx_v1.18.1_linux_arm64.tar.gz"
wget -q "$URL" -O mediamtx.tar.gz
tar xzf mediamtx.tar.gz
sudo install -m 755 mediamtx /usr/local/bin/mediamtx
mediamtx --version
```

### 6.3 본 저장소 배포

```bash
git clone https://github.com/squid55/rpi-camera-dvr.git
cd rpi-camera-dvr

DVR_USER=$USER   # 카메라 service를 돌릴 OS 사용자
sudo mkdir -p /srv/dvr/player /srv/dvr/thumbs /etc/mediamtx
sudo chown -R $DVR_USER:$DVR_USER /srv/dvr

sudo install -m 644 config/mediamtx.yml         /etc/mediamtx/
sudo install -m 644 config/nginx-dvr.conf       /etc/nginx/sites-available/dvr
sudo ln -sf /etc/nginx/sites-available/dvr      /etc/nginx/sites-enabled/dvr
sudo rm -f /etc/nginx/sites-enabled/default
sudo install -m 644 systemd/*.service           /etc/systemd/system/
sudo install -m 755 scripts/dvr-cleanup.sh      /usr/local/bin/
sudo install -m 755 scripts/trim_m3u8.py        /usr/local/bin/
sudo install -m 644 scripts/dvr-cleanup.cron    /etc/cron.d/dvr-cleanup
sudo install -m 644 -o $DVR_USER -g $DVR_USER web/player/index.html /srv/dvr/player/
sudo install -m 644 -o $DVR_USER -g $DVR_USER web/thumbs/thumbs.vtt /srv/dvr/thumbs/
sudo install -m 644 -o $DVR_USER -g $DVR_USER src/stream_server.py  /home/$DVR_USER/stream_server.py
```

### 6.4 환경값 치환

```bash
# Tailscale IP를 mediamtx.yml에 광고 (ICE candidate 등록)
sudo sed -i "s/100\.123\.127\.114/$(tailscale ip -4)/" /etc/mediamtx/mediamtx.yml

# camera-stream.service의 User= 와 ExecStart= 경로를 자기 환경에 맞게
sudo sed -i "s/User=rbpi3b/User=$DVR_USER/" /etc/systemd/system/camera-stream.service
sudo sed -i "s|/home/rbpi3b|/home/$DVR_USER|"   /etc/systemd/system/camera-stream.service
```

### 6.5 시작 + 검증

```bash
sudo systemctl daemon-reload
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl enable --now mediamtx
sudo systemctl enable --now camera-stream

# 검증
sudo systemctl is-active mediamtx camera-stream                  # 둘 다 active
ss -tlnp | grep -E ':(8090|8554|8889)'                           # 3 listeners
sudo journalctl -u mediamtx --since '1 minute ago' | grep 'path cam'
ls /srv/dvr/seg_*.ts | wc -l                                     # 30초 안에 5개 이상
ffprobe -v error -show_entries stream=profile $(ls /srv/dvr/seg_*.ts | head -1)
                                                                  # profile=Baseline
```

자세한 단계별 + 흔한 실패는 [`docs/INSTALL.md`](docs/INSTALL.md), 처음부터의 매뉴얼은 [`docs/SETUP-GUIDE.md`](docs/SETUP-GUIDE.md).

### 6.6 접속

```
http://<rpi-tailscale-ip>:8090/player/
```

---

## 7. Usage

| 동작 | 결과 | 내부 동작 |
|---|---|---|
| 페이지 열기 | 자동 WebRTC 라이브 (~0.2초) | `RTCPeerConnection` 생성 → `addTransceiver('video')` → `createOffer` → POST WHEP → SDP answer |
| 시크바 클릭/드래그 | "시간이동" 모드 | `seeking` event → 라이브 위치 ±3초 밖이면 `liveVideo` 숨김 → `dvrVideo`(HLS)가 그 위치 |
| "실시간으로" 빨간 버튼 | WebRTC 라이브 복귀 | `liveVideo` 다시 표시 + `dvrVideo.currentTime = hls.liveSyncPosition` |
| 일시정지 | 시간이동 모드 (현재 화면 정지) | `pause` event → `enterSeekMode` (자동 일시정지는 무시) |
| 풀스크린 | Plyr Fullscreen API | 표준 Fullscreen API 위임 |

UI 디테일:
- **LIVE 배지** — 라이브 모드일 때 빨간 `LIVE (WebRTC)`, 시크 모드일 때 회색 `시간이동`
- **시계** — 라이브 모드 = 현재 wall-clock, 시크 모드 = `frag.programDateTime + (currentTime - frag.start)*1000`
- **"실시간으로" 버튼** — 시크 모드에서만 표시 (`.show` class toggle)

---

## 8. Operations

### 8.1 일상 모니터링

```bash
sudo systemctl is-active mediamtx camera-stream
ss -tlnp | grep -E ':(8090|8554|8889)'
df -h /srv/dvr                                  # 정상은 ~25% (4h × 1Mbps)
uptime                                          # 1m < 4.0 정원
```

### 8.2 로그

```bash
sudo journalctl -u camera-stream -f             # ffmpeg 출력 + rpicam-vid stderr
sudo journalctl -u mediamtx -f                  # publisher/reader 이벤트
sudo tail -f /var/log/nginx/{access,error}.log  # 8090 클라이언트 활동
```

`mediamtx`의 정상 라인:
```
INF [path cam] stream is available and online, 1 track (H264)
INF [RTSP] [session ...] is publishing to path 'cam'
INF [WebRTC] [session ...] is reading from path 'cam'   # 클라이언트 접속 시
```

### 8.3 보존 정책 수동 실행

```bash
sudo /usr/local/bin/dvr-cleanup.sh              # 4h 초과 .ts 즉시 삭제 + m3u8 재정렬
ls /srv/dvr/seg_*.ts | wc -l                    # 정상 ~7200
```

### 8.4 보존 시간 변경

```bash
# 4h → 1h (예시)
sudo sed -i 's/RETAIN_HOURS:-4/RETAIN_HOURS:-1/' /usr/local/bin/dvr-cleanup.sh
# 또는 cron 환경변수로 override
echo 'RETAIN_HOURS=1' | sudo tee -a /etc/cron.d/dvr-cleanup
```

### 8.5 진단 flowchart (영상 안 보임)

```
                  영상 안 보임
                       │
         ┌─────────────┴─────────────┐
         │                           │
    8090 응답?                    아니오
    curl -I .../dvr.m3u8             │
         │                          nginx 다운 / 8090 점유 충돌
       200                          → systemctl status nginx
         │                          → ss -tlnp | grep :8090
   m3u8에 segment 있음?
   tail -5 dvr.m3u8
         │
        아니오 → ffmpeg/rpicam-vid 다운
                  → journalctl -u camera-stream -n 50
                  → systemctl restart camera-stream
        예
         │
   .ts에 SPS/PPS?
   ffprobe seg_*.ts
         │
        아니오 → ADR #3 깨짐
                  → rpicam-vid 옵션 재확인 (--inline 필수)
        예
         │
   브라우저 콘솔 에러?
         │
   "Failed to load m3u8" → mime types / CORS → docs/TROUBLESHOOTING §4
   "WHEP 405"            → MediaMTX webrtc 비활성 → mediamtx.yml 확인
   에러 없는데 검정      → H.264 profile 호환 → ADR #1
```

자세히는 [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md), 본 빌드 사례 6건은 [`docs/POST-MORTEM.md`](docs/POST-MORTEM.md).

---

## 9. Documentation map

처음 본다면 **순서대로 읽으면 자연스럽다**.

| # | 문서 | 무엇이 들어 있나 | 분량 |
|---|---|---|---|
| 1 | [CONCEPTS](docs/CONCEPTS.md) | HLS / DVR / LL-HLS / WebRTC / WebVTT 핵심 개념 | 입문 |
| 2 | [HARDWARE](docs/HARDWARE.md) | 보드(3B/4/5) · 카메라 · SD · SSD · 케이스 비교, 한국 쇼핑몰 + 추천 구성 3종 | 구매 가이드 |
| 3 | [SETUP-GUIDE](docs/SETUP-GUIDE.md) | OS 굽기부터 폰 시크까지 14단계 매뉴얼 | 처음 셋업 |
| 4 | [INSTALL](docs/INSTALL.md) | as-built 기준 압축본 (apt + MediaMTX + systemd) | 두 번째 이상 |
| 5 | [ARCHITECTURE](docs/ARCHITECTURE.md) | 데이터 흐름, 컴포넌트별 책임, dual-`<video>` 디자인 | 시스템 이해 |
| 6 | [STACK](docs/STACK.md) | 하드웨어/OS/도구 버전 표 + 라이선스 | 인용/감사용 |
| 7 | [IMPLEMENTATION-PLAN](docs/IMPLEMENTATION-PLAN.md) | 6단계 로드맵 + 위험 매트릭스 + ffmpeg 옵션 상세 | 확장 계획 |
| 8 | [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | 11 섹션 카탈로그 가이드 (카메라/ffmpeg/HLS/nginx/플레이어/SD/Tailscale/발열/명령어/FAQ) | 일반 진단 |
| 9 | [POST-MORTEM](docs/POST-MORTEM.md) | 2026-05-02 빌드 6 incidents | 사건 이력 |
| 10 | [REFERENCES](docs/REFERENCES.md) | 표준(RFC/W3C/Apple) + OSS NVR + 학술 논문 12편 | 참고 자료 |

---

## 10. Roadmap & status

### 10.1 완료 (2026-05-03 기준)

- **Phase 1 — MVP**: rpicam-vid → ffmpeg HLS → nginx → hls.js. 4h DVR 시크 동작.
- **Phase 1+ — WebRTC 통합**: MediaMTX + RTSP push + dual-`<video>` 토글. 라이브 0.2초.
- **Phase 3 — 보존 정책**: cron 10분 + `trim_m3u8.py`.
- **Phase 4 부분** — LIVE 배지, 절대 시각 표시.

### 10.2 미진행

- [ ] **Phase 2 — 썸네일 호버 (WebVTT)**: ffmpeg 추출 + ImageMagick montage + WebVTT 생성. 현재 `thumbs.vtt` placeholder만.
- [ ] **Phase 4 마감 — PWA**: manifest + service worker + 홈 아이콘.
- [ ] **Phase 5 — AI 이벤트 마커**: Jetson Orin YOLOv8 → webhook → 시크바 마커 표시.
- [ ] **Phase 6 — RPi 5 마이그레이션**: 1080p30 LL-HLS, NVMe HAT, 듀얼 IMX219 (CSI 2포트).

---

## 11. Risk register

| 리스크 | 영향 | 관측 가능성 | 완화책 |
|---|---|---|---|
| SD카드 마모 | 영상 손실 / 보드 read-only | `dmesg` I/O error | High-Endurance SD 또는 USB SSD 마운트 |
| RPi 3B 발열 throttle | fps 드롭 / ffmpeg 재시작 | `vcgencmd get_throttled != 0x0` | 방열판 + 작은 팬 |
| LOAD spike (1m > 4) | SSH 응답성 / WebRTC jitter | `uptime` 모니터링 | 720p15 1Mbps 유지 (ADR #5) |
| 정전 → 마지막 .ts 깨짐 | 마지막 1~2초 손실 | `journalctl --boot=-1` | UPS HAT 또는 graceful shutdown |
| WebRTC ICE 협상 실패 | HLS-fallback 5초 지연 | 브라우저 console + `pc.iceConnectionState` | `webrtcAdditionalHosts`에 Tailscale IP |
| Tailscale DERP relay 강제 | 대역 ↓, 지연 ↑ | `tailscale netcheck` | UPnP / IPv6 활성화 |
| 시계 어긋남 (NTP) | `program_date_time` 신뢰성 ↓ | `timedatectl status` | systemd-timesyncd / chrony 활성 유지 |
| nginx access log 누적 | / 파티션 압박 | `df -h /` | logrotate (apt 기본) |

---

## 12. Related projects & OSS NVR comparison

이 프로젝트는 [Multi-Board-Viewer](https://github.com/squid55/Multi-Board-Viewer)의 자매 프로젝트로, 라즈베리파이 카메라 노드에 한정된 **DVR + WebRTC** 레이어를 추가합니다. 멀티보드 뷰어 없이 단독으로 동작합니다.

비슷한 OSS NVR과 비교:

| 프로젝트 | 강점 | 약점 (본 프로젝트와 비교) |
|---|---|---|
| [Frigate](https://github.com/blakeblackshear/frigate) | AI 감지 + 객체 추적, Home Assistant 통합 | RPi 3B에 무거움 (Coral/EdgeTPU 권장), HLS 시크백 한정적 |
| [MotionEye](https://github.com/motioneye-project/motioneye) | 다채널 motion detection | MJPEG only, DVR/WebRTC 없음 |
| [ZoneMinder](https://github.com/ZoneMinder/zoneminder) | 풀-NVR 시스템, MySQL 기반 | 무겁고 복잡, RPi에 과함 |
| [picam](https://github.com/iizukanao/picam) | 경량 RPi 캡처/HLS | 시크/WebRTC 없음 |
| [OvenMediaEngine](https://github.com/AirenSoft/OvenMediaEngine) | LL-HLS + WebRTC 본격 라이브 | 주로 server-class, RPi 3B엔 과함 |

자세히는 [`docs/REFERENCES.md` §5](docs/REFERENCES.md).

---

## 13. License & contributing

본 저장소: **[MIT](LICENSE)**.

각 의존성의 라이선스는 [`docs/STACK.md` §라이선스 호환](docs/STACK.md).

기여:
- Issue: 증상 + 환경(`uname -a`, `mediamtx --version`, `ffmpeg -version`) + 재현 절차
- PR: 작은 단위로. README/docs 변경은 별도 PR 권장
- 코드 스타일: Python은 PEP 8, shell은 ShellCheck 통과, JS는 ESLint default

질문/논의는 [Issues](https://github.com/squid55/rpi-camera-dvr/issues) 또는 자매 프로젝트 [Multi-Board-Viewer](https://github.com/squid55/Multi-Board-Viewer/issues).

---

> 변경 이력 / release tag: [Releases](https://github.com/squid55/rpi-camera-dvr/releases)
