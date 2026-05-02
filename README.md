# rpi-camera-dvr

Twitch/YouTube-Live 수준의 **DVR(타임머신) + 무지연 라이브** IP카메라를 Raspberry Pi 3B + IMX219로 구현.

- 라이브: **WebRTC** (~0.2초 지연)
- 시간이동(시크백): **HLS** (4시간 누적, SD카드 저장)
- 폰/PC 브라우저에서 같은 페이지 안에서 자동 토글

> 멀티보드 카메라 시스템의 한 노드. 메인 메타 저장소: [Multi-Board-Viewer](https://github.com/squid55/Multi-Board-Viewer)

---

## 시스템 구조

```
[IMX219 카메라]
       │ MIPI CSI
       ▼
[Raspberry Pi 3B (aarch64, Trixie)]
  ├── rpicam-vid  (H.264 baseline, --inline, 2s GOP, 1Mbps, HW 인코더)
  │       │
  │       ▼ pipe
  ├── ffmpeg
  │     ├→ /srv/dvr/seg_*.ts + dvr.m3u8     (HLS DVR, EVENT 타입)
  │     └→ rtsp://localhost:8554/cam        (publish to MediaMTX)
  │
  ├── MediaMTX :8554 RTSP / :8889 WebRTC(WHEP)
  ├── nginx :8090   (HLS m3u8/.ts + 정적 player 서빙)
  └── cron 10분 주기 (4시간 보존 + m3u8 sync)
       │
       ▼ Tailscale (NAT 자동 통과, STUN/TURN 불필요)
[브라우저]
  player/index.html
    ├ liveVideo  ← WebRTC RTCPeerConnection (0.2s, 라이브 오버레이)
    └ dvrVideo   ← hls.js (시크백, 백그라운드에서 항상 라이브 끝 따라감)
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
docs/                      # 상세 문서
  ARCHITECTURE.md
  STACK.md
  INSTALL.md
  TROUBLESHOOTING.md
```

## 빠른 설치

전제: RPi OS Trixie 64-bit, IMX219 CSI 연결됨, Tailscale 가입됨.

```bash
sudo apt update
sudo apt install -y ffmpeg nginx rpicam-apps

# MediaMTX (arm64)
cd /tmp
wget https://github.com/bluenviron/mediamtx/releases/download/v1.18.1/mediamtx_v1.18.1_linux_arm64.tar.gz
tar xzf mediamtx_v1.18.1_linux_arm64.tar.gz
sudo mv mediamtx /usr/local/bin/

# 이 저장소
git clone https://github.com/squid55/rpi-camera-dvr.git
cd rpi-camera-dvr

sudo mkdir -p /etc/mediamtx /srv/dvr/player /srv/dvr/thumbs
sudo cp config/mediamtx.yml          /etc/mediamtx/
sudo cp config/nginx-dvr.conf        /etc/nginx/sites-available/dvr
sudo ln -sf /etc/nginx/sites-available/dvr /etc/nginx/sites-enabled/dvr
sudo rm -f /etc/nginx/sites-enabled/default
sudo cp systemd/*.service            /etc/systemd/system/
sudo cp scripts/dvr-cleanup.sh       /usr/local/bin/
sudo cp scripts/trim_m3u8.py         /usr/local/bin/
sudo cp scripts/dvr-cleanup.cron     /etc/cron.d/dvr-cleanup
sudo cp web/player/index.html        /srv/dvr/player/
sudo cp web/thumbs/thumbs.vtt        /srv/dvr/thumbs/
sudo cp src/stream_server.py         /opt/

# camera-stream.service의 ExecStart 경로를 /opt/stream_server.py로 맞춰 수정
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx camera-stream
sudo systemctl reload nginx
```

자세한 단계, 흔한 실패는 [docs/INSTALL.md](docs/INSTALL.md) 참고.

## 사용

브라우저로 `http://<rpi-tailscale-ip>:8090/player/` 접속.

| 동작 | 결과 |
|------|------|
| 페이지 열기 | 자동 WebRTC 라이브 (~0.2초) |
| 시크바 클릭/드래그 | 시간이동 모드 — HLS로 그 위치 재생 |
| "실시간으로" 빨간 버튼 | WebRTC 라이브 복귀 |
| 일시정지 | 시간이동 모드(현재 화면에서 정지) |

## 핵심 결정 (이 환경에 맞춘 트레이드오프)

| 결정 | 선택 | 이유 |
|------|------|------|
| H.264 profile | **Baseline** | WebRTC 호환성 (Chrome/Firefox/Safari) |
| GOP / segment | 2초 / 30프레임 | 시크 정확도 + HLS 표준 |
| 프레임레이트 | 15fps | RPi 3B CPU 한계 (LOAD ~1.8) |
| 비트레이트 | 1 Mbps (720p) | SD카드 4시간=1.8GB, Wi-Fi 부담 적음 |
| 보존시간 | 4시간 | "현실선" — SD카드 9.7GB 여유에서 안전 |
| HLS 모드 | EVENT (`hls_playlist_type event`) | 시크 가능 timeline + append-only |
| 인증 | Tailscale only | NAT 통과 + 전송 암호화 위임 |
| MJPEG 8080 | **제거** | RPi 3B CPU 부담으로 멀티보드 뷰어 패널 검정 처리 |

## 라이선스

MIT (별도 명시 전까지)

## 관련 문서

- [Architecture (시스템 구조 상세)](docs/ARCHITECTURE.md)
- [Stack (사용 기술/버전 표)](docs/STACK.md)
- [Install (설치 단계별)](docs/INSTALL.md)
- [Troubleshooting (구현 중 만난 6건의 이슈)](docs/TROUBLESHOOTING.md)
