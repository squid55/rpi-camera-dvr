# 문제 해결 가이드

증상 → 원인 → 해결 순으로 정리. 비슷한 문제가 여러 카테고리에 걸칠 수 있으니 검색(Ctrl+F) 권장.

---

## 0. 빠른 5단계 진단

문제가 생겼을 때 항상 이 순서로 체크하면 90%는 원인이 잡힌다.

```bash
# 1. 카메라 자체 동작?
vcgencmd get_camera                           # supported=1 detected=1
libcamera-hello -t 1000                        # 에러 메시지 보기

# 2. ffmpeg 서비스 살아있나?
systemctl is-active camera-dvr                 # active 여야
journalctl -u camera-dvr -n 30                 # 마지막 30줄 로그

# 3. 세그먼트가 만들어지고 있나?
ls -lt /srv/dvr/*.ts | head
stat /srv/dvr/dvr.m3u8                         # Modify 시각이 최근이어야

# 4. nginx가 m3u8을 서빙하나?
curl -I http://localhost:8090/dvr.m3u8         # 200 OK + Content-Type 확인

# 5. 디스크/온도는 멀쩡한가?
df -h /srv/dvr                                  # 90% 넘으면 위험
vcgencmd measure_temp                           # 80℃ 넘으면 throttle
vcgencmd get_throttled                          # 0x0 이 정상
```

---

## 1. 카메라 / libcamera 문제

### 1.1 `No camera available` 또는 `detected=0`

**원인 후보**:
- CSI 케이블 방향 거꾸로 (파란 면 위치 확인)
- 케이블 잠금 레버 미체결 (보드 측 또는 카메라 측)
- 케이블 손상 / 접점 더러움
- RPi 5 + 구형 두꺼운 CSI 케이블 (RPi 5는 얇은 케이블 전용)
- raspi-config에서 카메라 비활성

**해결**:
```bash
# 케이블 재체결 후
sudo reboot
vcgencmd get_camera

# 그래도 안 되면
sudo raspi-config            # Interface Options → Camera → Enable
dmesg | grep -i imx          # 센서 인식 로그
```

### 1.2 `libcamera-vid: command not found`

```bash
sudo apt install -y libcamera-apps libcamera-tools
```

### 1.3 `Failed to start camera... already in use`

다른 프로세스(예: 이전 ffmpeg)가 카메라를 잡고 있음.
```bash
ps aux | grep -E 'libcamera|ffmpeg' | grep -v grep
sudo systemctl stop camera-dvr
sudo pkill -9 -f libcamera-vid
```

### 1.4 영상이 너무 어둡다 / 노출 이상

```bash
libcamera-vid -t 0 \
  --awb auto \
  --exposure normal \
  --ev 0.5 \
  ...
```

옵션 전체: `libcamera-vid --help` 또는 https://www.raspberrypi.com/documentation/computers/camera_software.html

---

## 2. ffmpeg / 인코딩 문제

### 2.1 `Could not find encoder libx264`

RPi 5에서 SW 인코딩 시. apt 패키지에 빠져 있는 빌드가 있다.
```bash
sudo apt install -y ffmpeg libx264-dev
ffmpeg -encoders | grep 264         # libx264 표시 확인
```

### 2.2 ffmpeg가 자꾸 죽음 / restart 반복

```bash
journalctl -u camera-dvr -n 100 --no-pager
```

**자주 보이는 메시지와 의미**:

| 메시지 | 원인 |
|---|---|
| `Cannot allocate memory` | RAM 부족 (RPi 3B에서 1080p 시도) |
| `No space left on device` | SD카드 풀 |
| `Permission denied: /srv/dvr/...` | 폴더 소유권 |
| `Connection refused` | 입력 파이프 끊김 (libcamera-vid 죽음) |
| `Broken pipe` | 출력단 끊김 |

### 2.3 CPU 사용률 100% (RPi 5 SW 인코딩)

```bash
htop
# ffmpeg가 코어 4개 다 채우면서 throttle 발생
```

**해결**:
- 액티브 쿨러 / 케이스 환기 점검
- 해상도/비트레이트 낮추기 (1920×1080 → 1280×720, 3M → 2M)
- `-preset veryfast` → `ultrafast` (이미 ultrafast면 더는 못 줄임)
- `-threads 3` 으로 1코어 여유

### 2.4 영상은 나오는데 화면이 깨짐 (블록 노이즈)

키프레임 간격(GOP)이 너무 길면 시크 시 블록이 보일 수 있다.
```bash
# -g 옵션을 hls_time × fps의 정수배로
# 2초 세그먼트 + 30fps → -g 60
```

---

## 3. HLS / 시크 문제

### 3.1 시크가 부정확하다 (1~2초 어긋남)

`-hls_flags independent_segments` 가 빠져 있을 가능성. 각 세그먼트 시작이 키프레임이어야 시크 정확.

### 3.2 시크하면 영상이 멈춘다

- `dvr.m3u8`에 옛 .ts URL이 남아 있는데 cron이 실제 파일을 이미 지웠을 수 있다.
- `trim_m3u8.py`로 m3u8과 디스크를 동기화시켜야 한다.
- 임시 해결: cron 정리 주기를 늘리거나(예: 10분 → 30분) 보존 시간 + 5분 마진을 둔다.

### 3.3 LIVE 버튼을 눌러도 라이브로 안 감 / 시크바를 끌어도 라이브로 강제 복귀

`hls.liveSyncPosition`이 `NaN`이면 라이브가 아닌 VOD로 인식됐다는 뜻.
- 플레이리스트에 `#EXT-X-PLAYLIST-TYPE:VOD` 가 들어있으면 안 됨
- `#EXT-X-ENDLIST` 가 있으면 라이브가 끝났다고 판단
- 반대로 `EXT-X-PLAYLIST-TYPE` 자체가 **누락**되면 hls.js가 sliding window로 보고 backward seek을 막아버림 → DVR이 안 됨

```bash
grep -E "PLAYLIST-TYPE|ENDLIST" /srv/dvr/dvr.m3u8
```
DVR이 의도면 `#EXT-X-PLAYLIST-TYPE:EVENT` 한 줄이 있어야 한다. `VOD` 또는 `ENDLIST`가 같이 나오면 안 됨. ffmpeg 옵션에 `-hls_playlist_type event` 명시.

> 본 빌드 사례: [`POST-MORTEM.md` §3](POST-MORTEM.md#3-시크백-시-라이브-위치로-강제-복귀) — 시크바를 -50초로 끌어도 -3초로 자동 복귀하던 증상.

### 3.4 라이브 지연이 너무 크다 (10초 이상)

- 표준 HLS는 6~10초가 정상
- 줄이려면:
  - `-hls_time 1` (1초 세그먼트, 단 파일 수 폭증)
  - LL-HLS 적용 (RPi 5 권장)
  - `liveSyncDuration` 을 hls.js에서 더 작게

---

## 4. nginx / 네트워크 문제

### 4.1 브라우저에서 `404 Not Found` 또는 빈 화면

```bash
curl -I http://localhost:8090/dvr.m3u8
curl -I http://localhost:8090/player/
```

`200 OK`가 안 나오면:
```bash
sudo nginx -t                       # 설정 문법 OK?
sudo systemctl status nginx         # 살아있나?
sudo tail -f /var/log/nginx/error.log
```

자주 보는 원인:
- `root /srv/dvr;` 경로 오타
- `sites-enabled/` 심볼릭 링크 안 만들어짐
- 8090 포트 다른 프로세스가 점유 (`sudo lsof -i :8090`)

### 4.2 `Content-Type: text/html` 로 m3u8 응답이 옴

`types { ... }` 블록이 누락. SETUP-GUIDE §8.1 의 mime types 다시 확인.

### 4.3 CORS 에러 (다른 도메인에서 접근 시)

```
Access to XMLHttpRequest at '...' has been blocked by CORS policy
```

→ `add_header Access-Control-Allow-Origin *;` 가 location 안쪽에 있어야 일부 브라우저에서 동작. 위치 옮기거나 `always` 키워드 추가:
```nginx
add_header Access-Control-Allow-Origin * always;
```

### 4.4 LTE/외부에서 접속 안 됨

- Tailscale 연결 확인: `tailscale status`
- 휴대폰 Tailscale 앱이 연결됐는지
- 라우터/통신사 NAT가 막는다면 Tailscale은 자동 우회하지만 공유기 UPnP 꺼져 있으면 DERP relay로 폴백 → 속도 저하 발생

```bash
tailscale netcheck
tailscale status
```

---

## 5. 휴대폰 / 플레이어 문제

### 5.1 iOS Safari에서 재생 안 됨

iOS Safari는 hls.js 대신 **네이티브 HLS**로 재생한다. 단:
- `playsinline` 속성 없으면 풀스크린 자동 재생 강제
- HTTPS 아니면 일부 기능 제한
- LL-HLS는 iOS 14+ 만

```html
<video controls playsinline crossorigin>
```

### 5.2 Android Chrome에서 검은 화면

- hls.js 가 attach 됐는지 (`Hls.isSupported()` 확인)
- Console에 `Failed to load /dvr.m3u8` 같은 에러
- 보통 nginx mime type 또는 CORS 문제

### 5.3 Plyr 컨트롤이 안 보임

`<link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css">` 가 빠진 경우 자주 발생.

### 5.4 시크바 호버 미리보기 안 뜸

- `thumbs.vtt` 가 실제로 존재? (`curl :8090/thumbs/thumbs.vtt`)
- VTT 첫 줄이 `WEBVTT` 인지 (BOM 등 누락 X)
- Plyr 옵션에 `previewThumbnails: { enabled: true, src: ... }`
- 스프라이트 이미지 경로가 vtt 기준 상대경로로 맞는지

---

## 6. SD카드 / 디스크 문제

### 6.1 `No space left on device` (보존 시간 안 넘었는데도)

cron 정리가 동작 안 하고 있을 가능성:
```bash
sudo grep dvr-cleanup /var/log/syslog | tail
ls -la /var/log/dvr-thumbs.log     # 권한 문제로 cron이 실패하기도
```

또는 m3u8 파일 자체가 너무 커진 경우:
```bash
wc -l /srv/dvr/dvr.m3u8           # 수십만 줄이면 trim 필요
```

### 6.2 SD카드 읽기 전용으로 변함

수명 한계 + 부분 손상 → 자동 read-only 마운트.
```bash
mount | grep mmcblk0
dmesg | grep -i 'I/O error'
```

→ **SD카드 교체 + High Endurance 등급으로 업그레이드 권장**.

### 6.3 디스크 I/O 부하로 시스템 느려짐

```bash
iotop -ao
```
ffmpeg + montage(썸네일 합성)이 동시에 돌면 SD가 병목. **썸네일 cron 주기를 늘리거나** SSD로 이전.

---

## 7. Tailscale 문제

### 7.1 LAN에서는 되는데 LTE에서 안 됨

- 휴대폰 Tailscale 앱 ON 확인
- `tailscale status` 에서 휴대폰이 보이는지
- `tailscale ping <폰이름>` 으로 직접 확인
- 통신사가 IPv6/UDP을 강하게 막으면 DERP 사용 (속도 저하 가능)

### 7.2 MagicDNS 호스트네임으로 접속 안 됨

폰에서 `picam-dvr` 입력해도 안 풀리면 Tailscale 어드민에서 MagicDNS 활성화 확인.

→ 임시 해결: IP로 접속 (`http://100.X.X.X:8090/player/`)

---

## 8. 발열 / Throttle 문제

### 8.1 `vcgencmd get_throttled` 결과 해석

| 값 | 의미 |
|---|---|
| `0x0` | 정상 |
| `0x50000` | 과거에 throttle/under-voltage 발생, 현재는 OK |
| `0x80008` | 현재 throttle 발생 중 |

### 8.2 80℃ 넘는 경우

- 케이스 환기 / 액티브 쿨러 점검
- 옆에 다른 발열원(USB SSD 등) 멀리
- `vcgencmd measure_temp` 정기 모니터링 (Phase 3 대시보드 후보)

### 8.3 전원이 부족해 throttle (under-voltage)

- RPi 5는 **27W 정품 USB-C** 권장. 5V 3A 일반 전원은 RPi 4까지만
- 5V 2.5A 어댑터 + 카메라 + USB SSD 조합은 거의 확실히 부족
- USB 허브에 USB SSD 꽂는 것보다 보드 직결 권장

---

## 9. 진단 명령어 치트시트

```bash
# 시스템
uname -a
cat /etc/os-release
free -h
df -h
htop
iotop
vcgencmd measure_temp
vcgencmd get_throttled
vcgencmd get_camera

# 카메라
libcamera-hello -t 1000
libcamera-vid --help
v4l2-ctl --list-devices
dmesg | grep -i 'camera\|imx'

# DVR 서비스
systemctl status camera-dvr
journalctl -u camera-dvr -f
journalctl -u camera-dvr --since '10 min ago'
ls -lh /srv/dvr/ | tail
cat /srv/dvr/dvr.m3u8 | tail -20

# nginx
sudo nginx -t
sudo systemctl status nginx
sudo tail -f /var/log/nginx/{access,error}.log
sudo lsof -i :8090

# 네트워크
ip addr show
hostname -I
ss -tlnp                          # 어떤 포트가 열려 있나
ping -c 3 google.com

# Tailscale
tailscale status
tailscale ip -4
tailscale netcheck
sudo journalctl -u tailscaled -n 30
```

---

## 10. FAQ — 자주 묻는 질문

**Q. 영상에 소리도 같이 녹화되나?**
A. 기본 설정은 `-an` (오디오 끔). USB 마이크 + ALSA 입력으로 추가 가능. 단 SD카드 부담 증가.

**Q. 보드 재부팅하면 과거 영상도 보존되나?**
A. 그렇다. ffmpeg가 `append_list` 플래그로 기존 m3u8을 이어 받으므로 재시작 후에도 같은 플레이리스트가 유지된다.

**Q. 한 번에 여러 명이 봐도 되나?**
A. nginx는 정적 파일 서빙이라 동시 접속에 강하다. RPi 3B + 100Mbps + 1Mbps 비트레이트면 ~10명까진 무난.

**Q. 다른 보드(Jetson Nano 등)에서도 같은 방법으로 가능?**
A. 가능. 단 카메라 입력 단(libcamera 부분)을 GStreamer/v4l2로 교체. ffmpeg HLS 부분은 그대로.

**Q. WebRTC가 더 좋다는데?**
A. 지연은 좋지만 시크백/녹화가 어려움. 본 프로젝트 목표(DVR + 모바일)는 HLS가 더 잘 맞는다. WebRTC는 P2P/통화 용도에 더 적합.

**Q. 영상 다운로드 받게 하고 싶다**
A. 특정 시점 .ts 묶어서 mp4로 변환:
```bash
ffmpeg -i 'concat:seg_001.ts|seg_002.ts|...' -c copy clip.mp4
```
또는 m3u8 그대로 받게 하면 VLC가 자동 변환.

**Q. 비밀번호로 보호하고 싶다**
A. nginx에 `auth_basic` 추가:
```nginx
auth_basic "DVR";
auth_basic_user_file /etc/nginx/.htpasswd;
```
htpasswd는 `htpasswd -c /etc/nginx/.htpasswd 사용자명` (apt: `apache2-utils`)

**Q. 이상 감지 알림(움직임/사람 발견)은?**
A. Phase 5에서 다룰 부분. 외부 AI(Jetson Orin YOLOv8)가 감지하면 webhook으로 RPi에 마커 전송. 또는 **Frigate**(완성형 NVR)을 함께 사용.

**Q. 정전 후 부팅했더니 마지막 .ts가 깨졌다**
A. 보통 ffmpeg가 다음 부팅에서 새 세그먼트로 이어 붙이므로 손실은 최후 1~2초. UPS HAT 으로 graceful shutdown 가능.

**Q. SD카드 백업은 어떻게?**
A. 핵심은 `/srv/dvr` 자체가 아니라 **설정 파일**(systemd 유닛, nginx conf, cron). 그 외엔 항상 새로 굽는다는 가정으로.

**Q. RPi 위에서 직접 AI를 돌리고 싶다**
A. RPi 5 + Hailo AI HAT (~10만) 으로 YOLO 가능. 또는 RPi 5 단독으로도 YOLOv8n + ncnn 정도는 5~10fps.

---

## 11. 더 깊은 도움

- **Raspberry Pi 공식 포럼**: https://forums.raspberrypi.com/
- **Stack Overflow** — 검색: `raspberry pi ffmpeg hls`
- **Reddit r/raspberry_pi**: https://www.reddit.com/r/raspberry_pi/
- **r/homeautomation**, **r/homelab**: NVR 관련 논의 활발
- **이 프로젝트 Issues**: https://github.com/squid55/rpi-camera-dvr/issues

---

다음 → [`REFERENCES.md`](REFERENCES.md) (확장 자료/매뉴얼/논문)
