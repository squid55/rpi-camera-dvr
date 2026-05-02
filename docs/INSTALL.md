# Install

설치 환경 가정:
- Raspberry Pi OS Trixie (Debian 13) 64-bit (aarch64)
- IMX219 CSI 카메라 결선 + `dmesg | grep imx219`에 sensor 잡힘
- Tailscale 가입 + `tailscale status` active
- 네트워크 인터넷 연결

## 1. 패키지 설치

```bash
sudo apt update
sudo apt install -y ffmpeg nginx rpicam-apps libcamera-tools
```

확인:
```bash
rpicam-vid --help | head -2     # libcamera 기반 카메라 OK
ffmpeg -encoders 2>/dev/null | grep -E "h264_v4l2m2m|mjpeg"
```

## 2. MediaMTX 설치

```bash
cd /tmp
URL="https://github.com/bluenviron/mediamtx/releases/download/v1.18.1/mediamtx_v1.18.1_linux_arm64.tar.gz"
wget -q "$URL" -O mediamtx.tar.gz
tar xzf mediamtx.tar.gz
sudo install -m 755 -o root -g root mediamtx /usr/local/bin/mediamtx
```

## 3. 저장소 clone

```bash
cd ~
git clone https://github.com/squid55/rpi-camera-dvr.git
cd rpi-camera-dvr
```

## 4. 디렉토리 + 권한

DVR 데이터가 저장될 위치를 만들고 카메라 service 사용자(예: `rbpi3b`)가 쓸 수 있도록 함.

```bash
sudo mkdir -p /srv/dvr/player /srv/dvr/thumbs /etc/mediamtx
DVR_USER=rbpi3b   # 카메라 service를 돌릴 OS 사용자
sudo chown -R $DVR_USER:$DVR_USER /srv/dvr
```

## 5. 설정 파일 배포

```bash
# MediaMTX
sudo install -m 644 -o root -g root config/mediamtx.yml /etc/mediamtx/mediamtx.yml

# nginx
sudo install -m 644 -o root -g root config/nginx-dvr.conf /etc/nginx/sites-available/dvr
sudo ln -sf /etc/nginx/sites-available/dvr /etc/nginx/sites-enabled/dvr
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

# systemd units
sudo install -m 644 -o root -g root systemd/camera-stream.service /etc/systemd/system/
sudo install -m 644 -o root -g root systemd/mediamtx.service       /etc/systemd/system/

# 보존 정책
sudo install -m 755 -o root -g root scripts/dvr-cleanup.sh /usr/local/bin/dvr-cleanup.sh
sudo install -m 755 -o root -g root scripts/trim_m3u8.py    /usr/local/bin/trim_m3u8.py
sudo install -m 644 -o root -g root scripts/dvr-cleanup.cron /etc/cron.d/dvr-cleanup

# 정적 페이지
sudo install -m 644 -o $DVR_USER -g $DVR_USER web/player/index.html /srv/dvr/player/index.html
sudo install -m 644 -o $DVR_USER -g $DVR_USER web/thumbs/thumbs.vtt /srv/dvr/thumbs/thumbs.vtt

# 파이프라인 supervisor
sudo install -m 644 -o $DVR_USER -g $DVR_USER src/stream_server.py /home/$DVR_USER/stream_server.py
```

## 6. mediamtx.yml 사용자 환경 맞춤

`webrtcAdditionalHosts`에 자기 RPi의 Tailscale IP 추가:

```bash
sudo sed -i "s/100.123.127.114/$(tailscale ip -4)/" /etc/mediamtx/mediamtx.yml
```

또는 직접 편집:

```yaml
webrtcAdditionalHosts: [<your-tailscale-ip>]
```

## 7. 서비스 시작

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx
sudo systemctl enable --now camera-stream
```

검증:
```bash
sudo systemctl is-active mediamtx camera-stream
ss -tlnp | grep -E ":(8554|8889|8090)"
journalctl -u mediamtx --since "1 minute ago" | grep "path cam"
ls /srv/dvr/seg_*.ts | wc -l   # 10초 안에 5개 이상 나와야 정상
```

## 8. 브라우저 접속

```
http://<rpi-tailscale-ip>:8090/player/
```

WebRTC 라이브 자동 시작, 시크바로 4시간 안의 과거 시점 이동 가능.

## 흔한 실패

| 증상 | 원인 | 해결 |
|------|------|------|
| `path cam` 로그 안 나옴 | RTSP 포트 충돌 / mediamtx 미시작 | `journalctl -u mediamtx` 확인 |
| 8090에서 m3u8 200 OK인데 영상 안 보임 | `non-existing PPS 0` (ffprobe로 확인) | `--inline` 옵션 누락 — `src/stream_server.py` 확인 |
| WebRTC가 0.2s가 아닌 5s로 폴백 | ICE 협상 실패 / `webrtcAdditionalHosts` 누락 | 6단계 다시 |
| `EXT-X-PLAYLIST-TYPE` 없음 → 시크 시 0:01 리셋 | playlist_type 누락 | ffmpeg 옵션 `-hls_playlist_type event` 확인 |
| LOAD ≥ 6 | rpicam-vid가 yuv420 출력 + ffmpeg가 인코딩 | `--codec h264 --inline` 으로 RPi HW 인코더 사용 확인 |

자세한 트러블슈팅은 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) 참조.
