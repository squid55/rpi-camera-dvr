# Tech Stack

## 하드웨어

| 항목 | 모델 | 비고 |
|------|------|------|
| SBC | Raspberry Pi 3B (BCM2837, ARM Cortex-A53 4코어 1.2GHz, 1GB RAM) | 64-bit OS 사용 |
| 카메라 | Sony IMX219 (8MP, MIPI CSI-2) | 동작: 1280×720 / 15fps / 1Mbps |
| 저장 | microSD 16GB | High-Endurance 권장 (TBW ↑) |
| 네트워크 | 내장 Wi-Fi 2.4GHz / 100Mbps Ethernet | Tailscale direct P2P |

## OS / 시스템

| 항목 | 버전 |
|------|------|
| OS | Raspberry Pi OS (Debian 13 Trixie) 64-bit (aarch64) |
| 커널 | Linux 6.x |
| init | systemd |
| 시계 동기 | systemd-timesyncd (NTP active) — `EXT-X-PROGRAM-DATE-TIME` 신뢰성 |

## 캡처 / 인코딩

| 도구 | 버전 | 역할 |
|------|------|------|
| `rpicam-apps` (`rpicam-vid`) | apt 패키지 | libcamera 기반 캡처 + H.264 HW 인코딩 |
| libcamera | apt 패키지 | 카메라 stack |
| H.264 인코더 | RPi3 VideoCore IV `bcm2835-codec` v4l2m2m | profile=Baseline, level=4.0 |
| ffmpeg | apt (Debian Trixie 기본) | demux + HLS mux + RTSP push (`-c:v copy`만, 재인코딩 없음) |

## 미디어 서버

| 도구 | 버전 | 역할 |
|------|------|------|
| MediaMTX | v1.18.1 (linux_arm64) | RTSP ingest + WebRTC(WHEP) publish + RTP 패킷화 |
| nginx | apt | 정적 m3u8 / .ts / 플레이어 페이지 서빙 |

## 프로토콜

| 프로토콜 | 용도 | 포트 |
|----------|------|------|
| **HLS** (HTTP Live Streaming, RFC 8216) | DVR 시크백 | 8090/TCP (HTTP) |
| **WebRTC + WHEP** | 라이브 (~0.2초 지연) | 8889/TCP (시그널링), 8189/UDP (ICE) |
| RTSP | 내부 ffmpeg → MediaMTX publish | 8554/TCP (localhost only) |

## 클라이언트 (브라우저)

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| [hls.js](https://github.com/video-dev/hls.js) | 1.x (CDN) | HLS 디코딩 + MSE 재생 |
| [Plyr](https://github.com/sampotts/plyr) | 3.7.8 (CDN) | 비디오 컨트롤 UI (progress bar, fullscreen 등) |
| RTCPeerConnection | 브라우저 native | WebRTC 라이브 수신 |

## 표준

- **RFC 8216** — HTTP Live Streaming
- **WebVTT (W3C)** — 썸네일 트랙 (현재 Phase 2 미구현, placeholder만)
- **WHEP** (WebRTC-HTTP Egress Protocol) — IETF draft, MediaMTX/OBS 등이 사실상 표준
- **EXT-X-PROGRAM-DATE-TIME** — HLS 절대시각 태그 (segment에 wall-clock 표시)

## 자원 / 한계

| 자원 | RPi 3B 측정 |
|------|-------------|
| LOAD (4코어) | ~1.8 (idle 시 ~0.5 + 인코딩) |
| RAM | 약 470MB / 906MB |
| SD 쓰기 | ~125 KB/s (1Mbps × 보존중) |
| 동시 클라이언트 | 5명까지 부담 없음 (HLS는 정적, WebRTC는 SFU 아니라 N개 stream) |

## 라이선스 호환

| 컴포넌트 | 라이선스 |
|----------|----------|
| MediaMTX | MIT |
| ffmpeg (libavformat) | LGPL/GPL (빌드 옵션에 따라) |
| hls.js | Apache-2.0 |
| Plyr | MIT |
| nginx | BSD-2 |
| 본 저장소 | MIT (계획) |
