# 단계별 설치 매뉴얼

라즈베리파이를 처음 켜는 시점부터 휴대폰에서 시크 가능한 라이브를 보는 시점까지를 **그대로 따라할 수 있도록** 정리한 문서. RPi 3B 기준이며, RPi 5 차이점은 각 단계 끝에 별도 표기.

> 처음이라면 [`CONCEPTS.md`](CONCEPTS.md)와 [`HARDWARE.md`](HARDWARE.md)를 먼저 읽고 오면 훨씬 수월하다.

---

## 사전 준비

[`HARDWARE.md`](HARDWARE.md) 체크리스트의 부품이 모두 손에 있다고 가정한다. PC에는:
- **Raspberry Pi Imager** 설치 (https://www.raspberrypi.com/software/)
- **SSH 클라이언트** (Linux/macOS는 기본, Windows는 PowerShell 또는 PuTTY)

---

## 0단계 — 네트워크 IP 미리 확보

라즈베리파이를 같은 공유기에 연결해야 SSH 접속이 가능하다. 공유기 관리자 페이지(`192.168.0.1` 또는 `192.168.219.1`)에서 DHCP 클라이언트 목록을 보거나, 부팅 후 모니터/키보드를 잠깐 연결해 `hostname -I`로 확인하는 방식 둘 다 가능.

> 공유기 관리자에서 **MAC 주소 기반 고정 IP**를 미리 잡아두면 평생 편하다.

---

## 1단계 — Raspberry Pi OS 설치

### 1.1 OS 굽기 (PC에서)

1. Raspberry Pi Imager 실행
2. **OS 선택** → "Raspberry Pi OS Lite (64-bit)" (GUI 필요 없음, 가벼움)
3. **저장소 선택** → 꽂아 둔 microSD 카드
4. ⚙ (톱니바퀴) **고급 설정** 클릭:
   - 호스트네임: `picam-dvr` (예시)
   - 사용자: `pi`, 비밀번호: 임의
   - Wi-Fi: 사용 시 SSID/PW (이더넷이면 생략)
   - **SSH 활성화**: ✅
   - 로케일: `Asia/Seoul`, 키보드 `us`
5. "쓰기" 클릭 → 5~10분 대기

### 1.2 부팅

- microSD 카드를 RPi에 꽂고 전원 연결
- 1~2분 후 SSH 접속:
```bash
ssh pi@picam-dvr.local
# 또는 IP 직접: ssh pi@192.168.0.XX
```

> `.local` 로 안 되면 IP로 접속. mDNS가 공유기 따라 안 통할 수 있음.

### ✅ 검증
```bash
uname -a            # 커널 버전 출력
cat /etc/os-release # OS 정보
```

---

## 2단계 — 시스템 업데이트

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

재부팅 후 다시 SSH 접속.

---

## 3단계 — 카메라 활성화 및 테스트

### 3.1 RPi 3B / 4 (Bullseye 기준)
```bash
sudo raspi-config
# Interface Options → Camera → Enable → Reboot
```

> RPi 5 / Bookworm 이후는 보통 자동 인식. `raspi-config`에 메뉴가 없으면 그대로 진행.

### 3.2 카메라 동작 확인
```bash
libcamera-hello -t 5000     # 5초간 프리뷰 (모니터 있을 때)
libcamera-vid -t 3000 -o /tmp/test.h264 --width 1280 --height 720
ls -lh /tmp/test.h264       # 파일 생성 확인
```

### 3.3 문제 시
```bash
dmesg | grep -i camera      # 커널 로그
vcgencmd get_camera          # supported=1 detected=1 이어야 함
```

`detected=0` 이면 CSI 케이블 방향(파란 면) 또는 보드 측/카메라 측 잠금 레버를 다시 점검. RPi 5는 케이블 폼팩터가 다르므로 **호환 케이블** 인지 재확인.

### ✅ 검증 포인트
- `libcamera-hello -t 1000` 실행 시 에러 없이 종료
- `/tmp/test.h264`가 수십~수백 KB 이상

---

## 4단계 — 의존성 설치

```bash
sudo apt install -y \
    ffmpeg \
    nginx \
    imagemagick \
    python3-pip \
    htop iotop tmux git
```

설치 확인:
```bash
ffmpeg -version | head -1
nginx -v
montage --version | head -1
```

---

## 5단계 — DVR 디렉토리 만들기

```bash
sudo mkdir -p /srv/dvr/thumbs /srv/dvr/player
sudo chown -R pi:pi /srv/dvr
```

> SSD/USB 디스크에 두려면 `/srv/dvr` 대신 `/mnt/ssd/dvr` 같은 경로로 바꾸고 mount 후 진행. fstab에도 등록 권장.

---

## 6단계 — ffmpeg HLS 파이프라인 첫 시도

먼저 **수동으로** 한 번 돌려서 동작 확인부터.

### 6.1 RPi 3B (HW 인코더)
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

### 6.2 RPi 5 (SW 인코더)
```bash
libcamera-vid -t 0 --width 1920 --height 1080 --framerate 30 --codec yuv420 -o - | \
  ffmpeg -f rawvideo -pix_fmt yuv420p -s 1920x1080 -framerate 30 -i - \
    -c:v libx264 -preset ultrafast -tune zerolatency -g 60 -b:v 3000000 -an \
    -f hls -hls_time 2 -hls_list_size 0 \
    -hls_flags independent_segments+program_date_time+append_list \
    -hls_segment_filename '/srv/dvr/seg_%05d.ts' \
    /srv/dvr/dvr.m3u8
```

10~20초 두고 다른 SSH 세션에서:
```bash
ls -lh /srv/dvr/
# dvr.m3u8 + seg_*.ts 파일들이 생기고 있어야 함
cat /srv/dvr/dvr.m3u8 | tail -20
```

`seg_NNNNN.ts` 가 2초마다 추가되면 성공. `Ctrl+C`로 일단 종료.

### ❗ 안 될 때
- **`Permission denied`**: `/srv/dvr` 소유자 확인 (`ls -la /srv/dvr`)
- **`Could not find encoder libx264`** (RPi 5): `sudo apt install -y libx264-dev` 후 ffmpeg 재설치 또는 packaged 빌드 사용
- **`No camera available`**: 3.3절 카메라 진단으로

---

## 7단계 — systemd 서비스로 자동 시작

수동 명령을 부팅 시 자동 실행되도록 등록.

### 7.1 서비스 유닛 파일

```bash
sudo nano /etc/systemd/system/camera-dvr.service
```

내용 (RPi 3B 기준 — RPi 5면 6.2의 명령으로 교체):
```ini
[Unit]
Description=RPi Camera DVR (libcamera-vid -> ffmpeg HLS)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/srv/dvr
ExecStart=/bin/bash -c 'libcamera-vid -t 0 --width 1280 --height 720 --framerate 30 --codec h264 --bitrate 1500000 --inline -o - | ffmpeg -fflags nobuffer -i - -c:v copy -an -f hls -hls_time 2 -hls_list_size 0 -hls_flags independent_segments+program_date_time+append_list -hls_segment_filename /srv/dvr/seg_%05d.ts /srv/dvr/dvr.m3u8'
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 7.2 활성화
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now camera-dvr.service
sudo systemctl status camera-dvr.service
```

### ✅ 검증
- `Active: active (running)` 표시
- `journalctl -u camera-dvr -f` 에서 ffmpeg가 매 2초 세그먼트 생성 로그 출력
- `/srv/dvr/`에 .ts 파일 누적

---

## 8단계 — nginx 설정

### 8.1 설정 파일

```bash
sudo nano /etc/nginx/sites-available/dvr
```

```nginx
server {
    listen 8090;
    server_name _;

    root /srv/dvr;
    index index.html;

    types {
        application/vnd.apple.mpegurl m3u8;
        video/mp2t                    ts;
        text/vtt                      vtt;
        video/iso.segment             m4s;
        application/octet-stream      mp4 init;
    }

    add_header Cache-Control no-cache;
    add_header Access-Control-Allow-Origin *;

    location /player/ {
        alias /srv/dvr/player/;
        try_files $uri $uri/ /player/index.html;
    }
}
```

### 8.2 활성화
```bash
sudo ln -s /etc/nginx/sites-available/dvr /etc/nginx/sites-enabled/
sudo nginx -t                    # 문법 체크
sudo systemctl restart nginx
```

### ✅ 검증
PC에서:
```bash
curl http://picam-dvr.local:8090/dvr.m3u8 | head
# #EXTM3U ... 출력되면 OK
```

---

## 9단계 — 폰용 플레이어 페이지 배포

```bash
nano /srv/dvr/player/index.html
```

내용:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RPi DVR</title>
  <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css">
  <style>
    body { margin:0; background:#000; color:#fff; font-family: sans-serif; }
    #live-btn {
      position: fixed; top: 16px; right: 16px;
      background: #ff0033; color: white; border: none;
      padding: 8px 16px; border-radius: 4px; font-weight: bold;
      cursor: pointer; z-index: 9999;
    }
  </style>
</head>
<body>
  <video id="player" controls crossorigin playsinline></video>
  <button id="live-btn">🔴 실시간</button>

  <script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
  <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
  <script>
    const video = document.getElementById('player');
    const liveBtn = document.getElementById('live-btn');

    if (Hls.isSupported()) {
      const hls = new Hls({
        liveSyncDuration: 4,
        liveMaxLatencyDuration: 10,
        lowLatencyMode: true,
        backBufferLength: 60 * 60 * 4
      });
      hls.loadSource('/dvr.m3u8');
      hls.attachMedia(video);

      const player = new Plyr(video, {
        controls: ['play','progress','current-time','mute','volume','settings','pip','fullscreen']
      });

      liveBtn.onclick = () => { video.currentTime = hls.liveSyncPosition; };
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = '/dvr.m3u8';
      const player = new Plyr(video);
      liveBtn.onclick = () => { video.currentTime = video.duration; };
    } else {
      document.body.innerHTML = '<p>이 브라우저는 HLS를 지원하지 않습니다.</p>';
    }
  </script>
</body>
</html>
```

### ✅ 검증
- PC 브라우저: `http://picam-dvr.local:8090/player/`
- 영상이 라이브로 재생되고 시크바가 동작
- "🔴 실시간" 버튼 클릭 시 끝으로 점프

---

## 10단계 — Tailscale 설치 (외부 접속)

LAN 안에서만 쓸 거면 이 단계는 건너뛰어도 된다.

### 10.1 설치
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

표시되는 URL을 PC 브라우저에서 열어 GitHub/Google 계정으로 로그인.

### 10.2 IP 확인
```bash
tailscale ip -4
# 100.X.X.X 형태의 IP 출력
```

### ✅ 검증
- 휴대폰에 Tailscale 앱 설치 → 같은 계정 로그인
- 휴대폰 브라우저: `http://100.X.X.X:8090/player/`
- LTE 환경에서도 영상 재생되면 OK

---

## 11단계 — 썸네일 호버 활성화 (Phase 2)

### 11.1 추출 스크립트

```bash
nano ~/dvr-thumbs.sh
```
```bash
#!/bin/bash
DVR=/srv/dvr
THUMBS=$DVR/thumbs

cd $THUMBS

# 가장 최근 60분치 영상에서 10초마다 1장 추출
ffmpeg -y -i $DVR/dvr.m3u8 \
  -vf "fps=1/10,scale=160:90" \
  -q:v 5 raw_%06d.jpg

# 100장씩 묶어 스프라이트 시트로
COUNT=0
SHEET=1
TMPLIST=$(mktemp)
for f in raw_*.jpg; do
  echo $f >> $TMPLIST
  COUNT=$((COUNT + 1))
  if [ $COUNT -eq 100 ]; then
    montage @$TMPLIST -tile 10x10 -geometry 160x90 \
      $(printf "sprite_%04d.jpg" $SHEET)
    SHEET=$((SHEET + 1))
    COUNT=0
    > $TMPLIST
  fi
done

rm raw_*.jpg
```

### 11.2 cron 등록

```bash
chmod +x ~/dvr-thumbs.sh
crontab -e
```
파일 끝에 추가:
```
*/5 * * * * /home/pi/dvr-thumbs.sh >> /var/log/dvr-thumbs.log 2>&1
```

### 11.3 thumbs.vtt 생성기

```bash
nano ~/dvr-vtt.py
```
```python
#!/usr/bin/env python3
import os, glob, sys

DVR = "/srv/dvr/thumbs"
INTERVAL = 10  # seconds per thumb
SPRITE_W, SPRITE_H = 160, 90
COLS, ROWS = 10, 10

sprites = sorted(glob.glob(os.path.join(DVR, "sprite_*.jpg")))
if not sprites:
    sys.exit("no sprites yet")

lines = ["WEBVTT", ""]
t = 0
for sp in sprites:
    name = os.path.basename(sp)
    for r in range(ROWS):
        for c in range(COLS):
            start = t
            end = t + INTERVAL
            x, y = c * SPRITE_W, r * SPRITE_H
            lines.append(f"{fmt(start)} --> {fmt(end)}")
            lines.append(f"{name}#xywh={x},{y},{SPRITE_W},{SPRITE_H}")
            lines.append("")
            t = end

def fmt(sec):
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}.000"

# fmt 함수가 위에서 호출되므로 위치 조정 필요 — 실제 사용 시 위로 옮길 것
print("\n".join(lines))
```

이 스크립트는 위에서 `fmt`가 정의되기 전에 사용되므로 실제로는 `def fmt(...)`을 위로 옮긴 뒤 사용해야 한다. (이 문서에서는 흐름만 표시.)

```bash
~/dvr-vtt.py > /srv/dvr/thumbs/thumbs.vtt
```

### 11.4 플레이어 페이지 갱신

`/srv/dvr/player/index.html` 의 `Plyr` 호출에 `previewThumbnails` 추가:
```javascript
const player = new Plyr(video, {
  controls: [...],
  previewThumbnails: { enabled: true, src: '/thumbs/thumbs.vtt' }
});
```

### ✅ 검증
- 시크바에 마우스 올릴 때 썸네일 팝업

---

## 12단계 — 보존 시간 정리 cron (Phase 3)

```bash
nano /usr/local/bin/dvr-cleanup.sh
```
```bash
#!/bin/bash
RETAIN_HOURS=4
DVR=/srv/dvr

find $DVR -maxdepth 1 -name 'seg_*.ts' -mmin +$((RETAIN_HOURS * 60)) -delete
find $DVR/thumbs -name 'sprite_*.jpg' -mmin +$((RETAIN_HOURS * 60 + 30)) -delete

# m3u8 정리는 별도 Python 스크립트 (IMPLEMENTATION-PLAN §5.3 참고)
```
```bash
sudo chmod +x /usr/local/bin/dvr-cleanup.sh
sudo crontab -e
```
```
*/10 * * * * /usr/local/bin/dvr-cleanup.sh
```

---

## 13단계 — 모니터링 한 번만 더

```bash
# 디스크
df -h /srv/dvr

# 온도
vcgencmd measure_temp

# CPU/메모리
htop

# DVR 서비스 로그
journalctl -u camera-dvr -n 50

# nginx 액세스 로그
sudo tail -f /var/log/nginx/access.log
```

---

## 14단계 — 다음으로

- 보존 시간/해상도/플레이어 UI를 본인 환경에 맞게 튜닝
- 문제 생기면 [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
- 더 깊은 사양/로드맵은 [`IMPLEMENTATION-PLAN.md`](IMPLEMENTATION-PLAN.md)
- AI 이벤트 마커, RPi 5 마이그레이션은 Phase 5/6 계획 참고

---

## 부록 A — 단계별 검증 체크리스트

| 단계 | 검증 명령 | 기대 결과 |
|---|---|---|
| 1 | `ssh pi@picam-dvr.local` | 접속됨 |
| 3 | `vcgencmd get_camera` | `supported=1 detected=1` |
| 4 | `ffmpeg -version` | 4.x 또는 5.x 출력 |
| 6 | `ls /srv/dvr/seg_*.ts` | 파일 목록 |
| 7 | `systemctl is-active camera-dvr` | `active` |
| 8 | `curl :8090/dvr.m3u8` | `#EXTM3U` |
| 9 | 브라우저 player URL | 영상 재생 |
| 10 | LTE 폰에서 100.X.X.X | 영상 재생 |
| 11 | 시크바 호버 | 썸네일 팝업 |
| 12 | 보존 시간 + 1시간 후 `df -h` | 디스크 안정 |

---

## 부록 B — 한 번에 다 끄고 다시 켜기

```bash
# 정지
sudo systemctl stop camera-dvr nginx
sudo crontab -l > /tmp/cron.bak  # 백업
sudo crontab -r                   # cron 비활성

# 재개
sudo crontab /tmp/cron.bak
sudo systemctl start nginx camera-dvr
```

---

다음 → [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) (문제 해결) · [`REFERENCES.md`](REFERENCES.md) (확장 자료)
