# rpi-camera-dvr

라즈베리파이 IP카메라(IMX219 / Pi Camera Module)에 **치지직 / 트위치 / 유튜브 라이브 수준의 DVR(타임머신) 재생** 기능을 추가하는 프로젝트.

휴대폰으로 라이브를 보다가 시크바를 왼쪽으로 끌면 **방송 시작 시점(또는 최근 N시간)** 까지 되돌려 볼 수 있고, "**실시간**" 버튼 한 번이면 무지연(WebRTC) 라이브로 복귀 — 즉 치지직과 동일한 UX를 라즈베리파이 한 대로, SD카드 저장 기반으로 구현.

## 시스템 구조

```
[IMX219 카메라]
       │ MIPI CSI
       ▼
[Raspberry Pi 3B (aarch64, Trixie)]
  ├── rpicam-vid  (H.264 baseline, --inline, 2s GOP, 1Mbps, HW v4l2m2m)
  │       │
  │       ▼ pipe
  ├── ffmpeg  (-c:v copy 두 출력으로 fan-out, 재인코딩 0)
  │     ├→ /srv/dvr/seg_*.ts + dvr.m3u8     (HLS DVR, EVENT 타입)
  │     └→ rtsp://localhost:8554/cam        (publish to MediaMTX)
  │
  ├── MediaMTX :8554 RTSP / :8889 WebRTC(WHEP) / :8189 UDP ICE
  ├── nginx :8090   (HLS m3u8/.ts + 정적 player)
  └── cron 10분 주기 (4시간 보존 + m3u8 sync)
       │
       ▼ Tailscale (직접 P2P, NAT 통과)
[브라우저]
  player/index.html
    ├ liveVideo  ← WebRTC RTCPeerConnection (오버레이, ~0.2s 지연)
    └ dvrVideo   ← hls.js (시크백, 항상 attach 유지)
```

## 디렉토리 레이아웃

```
src/                       # 카메라/ffmpeg 파이프라인 supervisor
  stream_server.py
config/                    # 데몬 설정
  mediamtx.yml
  nginx-dvr.conf
systemd/                   # 서비스 정의
  camera-stream.service
  mediamtx.service
scripts/                   # 보존 정책 자동화
  dvr-cleanup.sh
  trim_m3u8.py
  dvr-cleanup.cron
web/                       # 정적 페이지 (nginx 8090)
  player/index.html
  thumbs/thumbs.vtt
docs/                      # 상세 문서 (아래 표 참조)
```

## 진행 상태

**2026-05-03 — 운영 중.** Phase 1 (MVP) + WebRTC 라이브 통합 완료. 깃허브 PR `feat/implementation-complete` 머지 진행 중.

미진행 Phase: 2(썸네일 호버 WebVTT), 4(LIVE 배지/PWA 일부), 5(AI 이벤트 마커), 6(RPi 5 마이그레이션). 자세한 단계는 [`docs/IMPLEMENTATION-PLAN.md`](docs/IMPLEMENTATION-PLAN.md).

## 핵심 결정 (이 환경에 맞춘 트레이드오프)

| 결정 | 선택 | 이유 |
|------|------|------|
| H.264 profile | **Baseline** | WebRTC 호환성 (Chrome/Firefox/Safari 디코더) |
| GOP / segment | 2초 / 30프레임 | 시크 정확도 + HLS 표준 |
| 프레임레이트 | 15fps | RPi 3B 4코어 한계 (LOAD ~1.8 안정) |
| 비트레이트 | 1 Mbps (720p) | SD카드 4시간=1.8GB, Wi-Fi 부담 적음 |
| 보존시간 | 4시간 | "현실선" — SD 9.7GB 여유 안에서 안전 |
| HLS 모드 | EVENT (`hls_playlist_type event`) | 시크 가능 timeline + append-only |
| 인증 | Tailscale only | NAT 통과 + 전송 암호화 위임 |
| MJPEG 8080 | **제거** | RPi 3B에서 H.264→MJPEG SW 트랜스코딩 부담 (LOAD 7.8 → 1.8 회복) |

## 측정값 (RPi 3B, IMX219, Trixie 64-bit)

| 항목 | 값 |
|------|---|
| LOAD (4코어) | ~1.8 (운영 중 안정) |
| RAM 사용 | ~470 MB / 906 MB |
| 라이브 지연 (WebRTC) | ~0.2초 |
| 라이브 지연 (HLS fallback) | ~3초 |
| HLS 세그먼트 누적률 | ~30 segments/min × 250KB |
| 4시간 DVR 사용량 | ~1.8 GB |
| 클라이언트 1명 대역 | ~2 Mbps (HLS+WebRTC 동시 수신) |

---

## 빠른 시작 (TL;DR)

전제: Raspberry Pi OS Trixie 64-bit, IMX219 CSI, Tailscale 가입.

```bash
sudo apt update
sudo apt install -y ffmpeg nginx rpicam-apps libcamera-tools

# MediaMTX (arm64)
cd /tmp
wget https://github.com/bluenviron/mediamtx/releases/download/v1.18.1/mediamtx_v1.18.1_linux_arm64.tar.gz
tar xzf mediamtx_v1.18.1_linux_arm64.tar.gz
sudo install -m 755 mediamtx /usr/local/bin/mediamtx

git clone https://github.com/squid55/rpi-camera-dvr.git
cd rpi-camera-dvr

sudo mkdir -p /srv/dvr/player /srv/dvr/thumbs /etc/mediamtx
sudo chown -R $USER:$USER /srv/dvr
sudo install -m 644 config/mediamtx.yml         /etc/mediamtx/mediamtx.yml
sudo install -m 644 config/nginx-dvr.conf       /etc/nginx/sites-available/dvr
sudo ln -sf /etc/nginx/sites-available/dvr      /etc/nginx/sites-enabled/dvr
sudo rm -f /etc/nginx/sites-enabled/default
sudo install -m 644 systemd/*.service           /etc/systemd/system/
sudo install -m 755 scripts/dvr-cleanup.sh      /usr/local/bin/dvr-cleanup.sh
sudo install -m 755 scripts/trim_m3u8.py        /usr/local/bin/trim_m3u8.py
sudo install -m 644 scripts/dvr-cleanup.cron    /etc/cron.d/dvr-cleanup
sudo install -m 644 web/player/index.html       /srv/dvr/player/
sudo install -m 644 web/thumbs/thumbs.vtt       /srv/dvr/thumbs/
sudo install -m 644 src/stream_server.py        /home/$USER/stream_server.py

# mediamtx.yml의 webrtcAdditionalHosts를 자기 Tailscale IP로 교체
sudo sed -i "s/100\.123\.127\.114/$(tailscale ip -4)/" /etc/mediamtx/mediamtx.yml

sudo systemctl daemon-reload
sudo systemctl reload nginx
sudo systemctl enable --now mediamtx camera-stream
```

검증:
```bash
sudo systemctl is-active mediamtx camera-stream
ss -tlnp | grep -E ":(8090|8554|8889)"
ls /srv/dvr/seg_*.ts | wc -l    # 10초 안에 5개 이상이면 정상
```

브라우저: `http://<rpi-tailscale-ip>:8090/player/`

자세한 단계는 [`docs/SETUP-GUIDE.md`](docs/SETUP-GUIDE.md) 또는 [`docs/INSTALL.md`](docs/INSTALL.md).

## 사용

| 동작 | 결과 |
|------|------|
| 페이지 열기 | 자동 WebRTC 라이브 (~0.2초) |
| 시크바 클릭/드래그 | 시간이동 모드 — HLS로 그 위치 재생 |
| "실시간으로" 빨간 버튼 | WebRTC 라이브 복귀 |
| 일시정지 | 시간이동 모드 (현재 화면에서 정지) |

---

## 📚 문서 구조

처음 본다면 **순서대로 읽으면 자연스럽다**.

| # | 문서 | 무엇이 들어 있나 |
|---|---|---|
| 1 | **[CONCEPTS](docs/CONCEPTS.md)** | HLS / DVR / LL-HLS / WebRTC / WebVTT 등 **핵심 개념을 그림과 표로 설명**. 처음이라면 여기부터. |
| 2 | **[HARDWARE](docs/HARDWARE.md)** | 보드(3B/4/5) · 카메라 · SD카드 · SSD · 케이스 비교. 한국 쇼핑몰 + **추천 구성 3종(예산/균형/풀스펙)**. |
| 3 | **[SETUP-GUIDE](docs/SETUP-GUIDE.md)** | OS 굽기부터 폰에서 시크 동작 확인까지 **그대로 따라할 수 있는 14단계 매뉴얼**. 단계별 검증 명령 포함. |
| 4 | **[INSTALL](docs/INSTALL.md)** | as-built 기준 설치 단계 + apt/MediaMTX/systemd. (SETUP-GUIDE의 implementation-ready 압축본) |
| 5 | **[ARCHITECTURE](docs/ARCHITECTURE.md)** | 데이터 흐름, 컴포넌트별 책임, dual-`<video>` 토글 디자인의 근거. |
| 6 | **[STACK](docs/STACK.md)** | 하드웨어/OS/캡처/인코딩/미디어서버/프로토콜/클라이언트 라이브러리 **버전 표 + 라이선스**. |
| 7 | **[IMPLEMENTATION-PLAN](docs/IMPLEMENTATION-PLAN.md)** | 더 깊은 사양 · 6단계 로드맵 · 위험 매트릭스 · ffmpeg 옵션 상세. |
| 8 | **[TROUBLESHOOTING](docs/TROUBLESHOOTING.md)** | **빠른 5단계 진단** + 카테고리별 흔한 증상/해결 + FAQ + 진단 명령어 치트시트. |
| 9 | **[POST-MORTEM](docs/POST-MORTEM.md)** | 2026-05-02 빌드에서 만난 **6건의 결정적 사건 (post-mortem)** — 같은 함정을 반복하지 않기 위한 이력 기록. |
| 10 | **[REFERENCES](docs/REFERENCES.md)** | 표준(RFC/W3C/Apple) · 도구 공식 문서 · 한국어 자료 · 비슷한 OSS NVR · **학술 논문 12편**. |

---

## 관련 프로젝트

이 프로젝트는 [Multi-Board-Viewer](https://github.com/squid55/Multi-Board-Viewer)의 자매 프로젝트로, 라즈베리파이 카메라 노드에 한정된 DVR + WebRTC 레이어를 추가합니다. 멀티보드 뷰어 없이 단독으로 동작합니다.

비슷한 컨셉의 OSS NVR 들과의 비교/참고 코드는 [`REFERENCES.md` §5](docs/REFERENCES.md) 참조 (Frigate, MotionEye, ZoneMinder, picam, OvenMediaEngine 등).

---

## 라이선스

[MIT](LICENSE)
