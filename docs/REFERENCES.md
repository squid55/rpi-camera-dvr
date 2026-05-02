# 확장 레퍼런스 — 매뉴얼 · 자료 · 논문

이 프로젝트를 만들면서 참고한, 그리고 더 깊이 들어가고 싶을 때 도움이 될 자료 모음. 가능하면 **공식 1차 자료**를 우선 표기하고, 검색이 필요한 자료는 검색어 형태로만 남겼다.

---

## 1. 표준 / 사양 문서

### HLS / LL-HLS
- **RFC 8216** — HTTP Live Streaming (1차 사양)
  https://datatracker.ietf.org/doc/html/rfc8216
- **HLS 2nd Edition Draft** — LL-HLS 포함 (Pantos)
  https://datatracker.ietf.org/doc/html/draft-pantos-hls-rfc8216bis
- **Apple Streaming Portal** — 공식 도구·도큐먼트·예제
  https://developer.apple.com/streaming/
- **Apple LL-HLS 가이드**
  https://developer.apple.com/documentation/http-live-streaming/enabling-low-latency-http-live-streaming-hls
- **Apple WWDC 2020 — Session 10229** "What's new in HTTP Live Streaming"
  https://developer.apple.com/videos/play/wwdc2020/10229/
- **Apple WWDC 2019 — Session 502** "Low-Latency HLS Preview"
  https://developer.apple.com/videos/play/wwdc2019/502/

### 주변 표준
- **WebVTT (W3C Recommendation)** — 자막/썸네일 트랙
  https://www.w3.org/TR/webvtt1/
- **MSE (Media Source Extensions)** — 브라우저 비디오 버퍼링 API
  https://www.w3.org/TR/media-source-2/
- **MPEG-DASH (ISO/IEC 23009-1)** — DASH 표준 페이지
  https://www.iso.org/standard/79329.html
- **CMAF (ISO/IEC 23000-19)** — DASH/HLS 공통 컨테이너
- **MPEG-2 Transport Stream (ISO/IEC 13818-1)** — .ts 컨테이너 사양

---

## 2. 도구 공식 문서

### 인코딩 / 패키징
- **ffmpeg HLS muxer**: https://ffmpeg.org/ffmpeg-formats.html#hls-2
- **ffmpeg 본 도큐먼트**: https://ffmpeg.org/ffmpeg.html
- **ffmpeg Wiki — HLS 가이드**: https://trac.ffmpeg.org/wiki/StreamingGuide
- **GStreamer hlssink2**: https://gstreamer.freedesktop.org/documentation/hls/hlssink2.html
- **MediaMTX (RTSP/HLS/WebRTC 통합 서버)**: https://github.com/bluenviron/mediamtx
- **nginx-rtmp-module** (옛 방식): https://github.com/arut/nginx-rtmp-module
- **Bento4** (mp4/CMAF 도구): https://www.bento4.com/

### 라즈베리파이 카메라
- **공식 카메라 소프트웨어 가이드**: https://www.raspberrypi.com/documentation/computers/camera_software.html
- **libcamera 프로젝트**: https://libcamera.org/
- **picamera2 (파이썬)**: https://github.com/raspberrypi/picamera2
- **공식 매뉴얼 (PDF)**: https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
- **V4L2 (Linux Video API)**: https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html

### 플레이어
- **hls.js GitHub**: https://github.com/video-dev/hls.js
- **hls.js API 문서**: https://github.com/video-dev/hls.js/blob/master/docs/API.md
- **hls.js 데모/플레이그라운드**: https://hls-js.netlify.app/demo/
- **Plyr GitHub**: https://github.com/sampotts/plyr
- **Plyr 옵션 (썸네일 등)**: https://github.com/sampotts/plyr#options
- **video.js GitHub**: https://github.com/videojs/video.js
- **video.js HLS plugin**: https://github.com/videojs/http-streaming
- **Shaka Player**: https://github.com/shaka-project/shaka-player
- **JW Player (상용 참고)**: https://docs.jwplayer.com/

### 웹 서버
- **nginx 공식 문서**: https://nginx.org/en/docs/
- **nginx HTTP module (정적 파일)**: https://nginx.org/en/docs/http/ngx_http_core_module.html

### 네트워크
- **Tailscale 도큐먼트**: https://tailscale.com/kb/
- **Tailscale 라즈베리파이 가이드**: https://tailscale.com/kb/1174/install-debian
- **WireGuard (Tailscale 기반)**: https://www.wireguard.com/

---

## 3. 한국어 자료

### 기술 블로그 (도메인)
- **NAVER D2** — 라이브 스트리밍 / 비디오 / 미디어 관련 글 다수
  https://d2.naver.com/
- **카카오 기술블로그** — 라이브 방송 / HLS / DASH 연재
  https://tech.kakao.com/
- **우아한형제들 기술블로그** — 라이브 커머스 도입기
  https://techblog.woowahan.com/
- **토스 기술블로그** — 미디어/네트워크 인프라 글
  https://toss.tech/
- **당근마켓 기술블로그** — 비디오 처리 사례
  https://medium.com/daangn
- **라인 기술블로그** — 글로벌 라이브 스트리밍 글
  https://engineering.linecorp.com/ko/blog
- **쏘카 기술블로그** — 실시간 영상/IoT 카테고리
  https://tech.socarcorp.kr/
- **아프리카TV 미디어 R&D** — HLS/DASH 운영 사례 (구글 검색 권장)

> 위 도메인 안에서 검색어 추천: `HLS`, `라이브 방송`, `LL-HLS`, `DVR`, `타임머신`, `MediaMTX`, `WebRTC` 등.

### 한국어 동영상 강의 / 튜토리얼
- YouTube 검색: "라즈베리파이 카메라 스트리밍", "라즈베리파이 ffmpeg HLS"
- Inflearn / Class101: "라즈베리파이 IoT" 강의 다수
- 노마드 코더 채널: 웹 스트리밍 관련 종종

### 라즈베리파이 한국 커뮤니티
- **라즈베리파이 한국 정보 카페**: 네이버 카페 검색 (검색어: `라즈베리파이 정보`)
- **DC 라즈베리파이 갤러리**: 트러블슈팅 사례 다수
- **메이커뉴스**: https://www.makernews.com/

### 한국어 책 (검색 키워드만)
- "라즈베리파이로 시작하는 IoT" 류 입문서
- "한 권으로 끝내는 라즈베리파이"
- "라즈베리파이 5 활용서" (출간 시점에 따라)

> 정확한 ISBN/저자/출판사는 책마다 다르고 빠르게 바뀌므로 교보문고/예스24에서 위 키워드로 검색.

---

## 4. 영어 튜토리얼 / 블로그

### 미디어 인프라 회사 블로그 (퀄리티 높음)
- **Mux 엔지니어링 블로그**: https://www.mux.com/blog
  → "How HLS works", "Low-Latency HLS", "DVR" 등 검색
- **Bitmovin 블로그**: https://bitmovin.com/blog/
  → DASH/HLS/LL-HLS/CMAF 시리즈
- **Wowza 지식 베이스**: https://www.wowza.com/docs
  → DVR 설정 가이드 (자사 서버 기준이지만 개념 학습용)
- **Akamai 미디어 블로그**: https://www.akamai.com/blog
- **Cloudflare Stream 블로그**: https://blog.cloudflare.com/tag/stream/
- **video.dev**: https://video.dev/ (hls.js 팀 주도 컨퍼런스)

### 학습용 사이트
- **Howard Wright — Learning HLS**: 시리즈 검색 권장
- **Frame.io Insider**: 영상 워크플로우 전반
- **OTTVerse**: https://ottverse.com/ — DASH/HLS 기술 글 풍부
- **Demuxed (컨퍼런스)**: https://demuxed.com/ (영상 라이브)

### Stack Overflow 검색어
- `[hls] dvr`
- `[ffmpeg] hls list_size`
- `[hls.js] livesyncposition`
- `[raspberry-pi] libcamera ffmpeg`

---

## 5. 비슷한 오픈소스 프로젝트 (공부용)

직접 쓰지는 않더라도 **소스를 읽으면 많이 배운다**.

| 프로젝트 | 특징 | URL |
|---|---|---|
| **Frigate** | AI(YOLO) 내장 NVR, RTSP→HLS/MSE | https://github.com/blakeblackshear/frigate |
| **MotionEye** | 클래식 모션 감지 NVR | https://github.com/motioneye-project/motioneye |
| **Shinobi** | Node.js 기반 NVR/CCTV | https://github.com/ShinobiCCTV/Shinobi |
| **ZoneMinder** | 가장 오래된 OSS NVR | https://github.com/ZoneMinder/zoneminder |
| **Scrypted** | Home Assistant 친화 NVR | https://github.com/koush/scrypted |
| **Viseron** | RTSP NVR + 객체 감지 | https://github.com/roflcoopter/viseron |
| **go2rtc** | RTSP/RTMP/HLS/WebRTC 라우터 | https://github.com/AlexxIT/go2rtc |
| **Janus Gateway** | WebRTC 게이트웨이 | https://github.com/meetecho/janus-gateway |
| **OvenMediaEngine** | 한국 AirenSoft, LL-HLS 강함 | https://github.com/AirenSoft/OvenMediaEngine |
| **Pion** | Go 기반 WebRTC 라이브러리 | https://github.com/pion/webrtc |

특히 **OvenMediaEngine**(한국팀) 은 LL-HLS / LL-DASH 구현 레퍼런스로 매우 좋다.
**Frigate** 는 "AI 이벤트 마커" Phase 5 구현 시 거의 그대로 차용 가능.

### 카메라 펌웨어 / 알찬 토이 프로젝트
- **uStreamer**: https://github.com/pikvm/ustreamer (저지연 MJPEG)
- **mediamtx + Pi**: https://github.com/bluenviron/mediamtx + raspberrypi 예제
- **picam (개인 NVR)**: https://github.com/iizukanao/picam (HLS DVR 직접 구현, 본 프로젝트 컨셉과 매우 유사)

> **picam** 은 본 프로젝트와 거의 동일한 목표로 만들어진 한국·일본 메이커 사이드 프로젝트다. 코드를 한 번 훑어보면 자체 구현 vs ffmpeg 차이를 빠르게 이해할 수 있다.

---

## 6. 학술 논문

### HTTP Adaptive Streaming 서베이
- **Bentaleb, A., et al.** "A Survey on Bitrate Adaptation Schemes for Streaming Media Over HTTP."
  *IEEE Communications Surveys & Tutorials*, 21(1), 2019.
- **Sodagar, I.** "The MPEG-DASH Standard for Multimedia Streaming Over the Internet."
  *IEEE MultiMedia*, 2011.
- **Stockhammer, T.** "Dynamic Adaptive Streaming over HTTP — Standards and Design Principles."
  *ACM MMSys 2011*.

### 저지연 라이브 스트리밍
- **Bentaleb, A., Akcay, M.N., Lim, M., et al.** "Common Media Client Data (CMCD) and Low-Latency CMAF Streaming."
  *IEEE Multimedia*, 2022.
- **Bouzakaria, N., Concolato, C., Le Feuvre, J.** "Overhead and Performance of Low Latency Live Streaming Using MPEG-DASH."
  *Multimedia Systems Journal*.

### DVR / 타임시프트
- **Lederer, S., Müller, C., Timmerer, C.** "Dynamic Adaptive Streaming over HTTP Dataset."
  *ACM MMSys 2012*.
- **Begen, A.C., et al.** "Watching Video over the Web: Part 1 — Streaming Protocols."
  *IEEE Internet Computing*, 2011.

### 엣지 비디오 / IP 카메라
- **Ananthanarayanan, G., et al.** "Real-time Video Analytics: The Killer App for Edge Computing."
  *IEEE Computer*, 2017.
- **Hung, C., et al.** "VideoEdge: Processing Camera Streams using Hierarchical Clusters."
  *IEEE/ACM SEC 2018*.
- **Jang, S.Y., et al.** "MARVEL: Towards Low-Cost Real-Time Mobile Video-Based Augmented Reality."
  *IEEE Internet Computing*, 2018.

### 한국 학회 (KSC, KCC, JKMS) 검색어
- "HLS DVR"
- "라이브 스트리밍 저지연"
- "엣지 카메라 분석"
- "라즈베리파이 영상 처리"

> DBpia, RISS, KISS 등에서 위 키워드 검색 시 KSII Transactions, JKIIT 등 한국어 논문 다수.

### 논문 검색 사이트
- **Google Scholar**: https://scholar.google.com/
- **Semantic Scholar**: https://www.semanticscholar.org/
- **DBLP** (저자별 출판물): https://dblp.org/
- **arXiv** (CS preprint): https://arxiv.org/list/cs.MM/recent

---

## 7. 책 / 장편 가이드

### 영어
- **"Learning HTTP Live Streaming"** — O'Reilly (오래됐지만 기본 개념 좋음)
- **"FFmpeg Basics"** — Frantisek Korbel (ffmpeg 명령어 레퍼런스)
- **"Video Encoding by the Numbers"** — Jan Ozer (인코딩 파라미터 튜닝)
- **"Real-time Communication with WebRTC"** — O'Reilly

### 무료 e-Book / 가이드
- **Howard Wright "Streaming 101"**: https://howvideo.works/
  → 영상 코덱부터 HLS/DASH까지 그림으로 풀어 줌. 무료, **강력 추천**.
- **Mux "Streaming Video Manual"**: https://www.mux.com/streaming-video-manual

---

## 8. 커뮤니티 / 포럼

| 곳 | URL | 비고 |
|---|---|---|
| Raspberry Pi 공식 포럼 | https://forums.raspberrypi.com/ | 카메라 트러블슈팅 |
| r/raspberry_pi | https://www.reddit.com/r/raspberry_pi/ | 일반 질문 |
| r/homelab | https://www.reddit.com/r/homelab/ | NVR 사례 |
| r/homeautomation | https://www.reddit.com/r/homeautomation/ | Frigate 사용자 많음 |
| Frigate Discord | (Frigate GitHub README 링크) | AI NVR 활용 |
| Tailscale Forum | https://forum.tailscale.com/ | VPN 트러블슈팅 |
| Stack Overflow | `[hls.js]`, `[ffmpeg]`, `[raspberry-pi]` | 검증된 답변 |

---

## 9. 동영상 / 강의

### YouTube 채널 (검색용)
- **ExplainingComputers** — 라즈베리파이 일반
- **NetworkChuck** — 홈랩/네트워크
- **Jeff Geerling** — 라즈베리파이 심화 (NVMe HAT 리뷰 다수)
- **Demuxed** — 영상 스트리밍 컨퍼런스 (LL-HLS 토크 있음)
- **Mux** — HLS 입문 영상

### Apple WWDC (이미 §1에 일부)
- 2016 — 504 "Advances in HTTP Live Streaming"
- 2017 — 504 "Advances in HTTP Live Streaming"
- 2019 — 502 "Advances in HTTP Live Streaming"
- 2020 — 10229 "What's new in HTTP Live Streaming" (LL-HLS)
- 2021/2022/2023 — 매년 HLS 세션 있음

---

## 10. 본 프로젝트 내부 문서 색인

| 문서 | 내용 |
|---|---|
| [README](../README.md) | 프로젝트 개요 + 빠른 진입점 |
| [CONCEPTS](CONCEPTS.md) | 핵심 개념 / HLS / DVR / LL-HLS 원리 |
| [HARDWARE](HARDWARE.md) | 보드 · 카메라 · SD · 쇼핑 가이드 |
| [SETUP-GUIDE](SETUP-GUIDE.md) | 단계별 설치 매뉴얼 |
| [IMPLEMENTATION-PLAN](IMPLEMENTATION-PLAN.md) | 사양 · 로드맵 · 위험 매트릭스 |
| [TROUBLESHOOTING](TROUBLESHOOTING.md) | 문제 해결 + FAQ |
| [REFERENCES](REFERENCES.md) | 이 문서 (확장 자료) |

---

## 11. 변경 이력

| 일자 | 내용 |
|---|---|
| 2026-05-02 | 최초 작성 |
