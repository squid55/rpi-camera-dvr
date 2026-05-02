# Post-mortem (구현 중 실제로 만난 6건의 결정적 사건)

> 일반적인 트러블슈팅 카탈로그는 [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md). 이 문서는 그것과 별개로, **2026-05-02 ~ 2026-05-03 빌드에서 한 번씩 발생했던 구체적 사건과 그 결정타**를 시간순으로 기록한 post-mortem. 같은 함정을 반복하지 않기 위함.

본 시스템을 RPi 3B에 처음 셋업하면서 다음 6건이 차례로 막혔고, 그 해결이 곧 최종 디자인이 됨.

---

## 1. 카메라 디바이스 단일 점유 충돌

**증상**: 새로 추가하려는 ffmpeg pipeline의 `rpicam-vid`가 즉시 종료. 기존 멀티보드 뷰어용 `camera-stream.service`가 이미 카메라를 잡고 있음.

**원인**: libcamera는 한 프로세스만 카메라를 점유 가능. 두 개의 `rpicam-vid` 동시 불가.

**해결**: 한 ffmpeg 인스턴스가 **단일 캡처에서 모든 출력을 만들도록** 통합. `rpicam-vid → ffmpeg → [HLS 파일] + [RTSP push]`.

```python
# stream_server.py가 단일 supervisor로 rpicam-vid + ffmpeg 둘 다 spawn
rpicam = subprocess.Popen(["rpicam-vid", "--codec", "h264", "--inline", ...], stdout=PIPE)
ffmpeg = subprocess.Popen([..., "-i", "-", ...], stdin=rpicam.stdout, ...)
```

---

## 2. HLS 세그먼트가 SPS/PPS 누락 → 검정 화면

**증상**: hls.js가 m3u8 / .ts 정상 fetch (HTTP 200). 그런데 video element가 검정. ffprobe로 .ts 검사하면:

```
[h264 @ ...] non-existing PPS 0 referenced
[h264 @ ...] decode_slice_header error
[h264 @ ...] no frame!
```

**원인**: ffmpeg `h264_v4l2m2m` 인코더는 SPS/PPS를 첫 번째 packet에만 출력하고 이후 segment에는 안 넣음. ffmpeg HLS muxer는 그걸 매 세그먼트 시작에 inject하지 않음.

**시도1 실패**: `-bsf:v dump_extra=freq=keyframe` — v4l2m2m이 ffmpeg에 extradata를 보고하지 않아 BSF가 dump할 게 없음.

**해결**: rpicam-vid가 직접 H.264 인코딩하면서 `--inline` 옵션 사용. 매 keyframe에 SPS/PPS NAL을 자동 inject. ffmpeg는 단순 `-c:v copy`로 mux만.

```
rpicam-vid --codec h264 --inline --intra 30 --bitrate 1000000
```

ffprobe에서 `non-existing PPS` 0건, profile=Baseline level=40로 깔끔히 나오면 OK.

---

## 3. 시크백 시 라이브 위치로 강제 복귀

**증상**: 시크바를 -50초로 끌어도 1초 안에 -3초로 자동 복귀. 과거 영상 재생 불가.

**원인**: m3u8에 `EXT-X-PLAYLIST-TYPE` 태그가 없으면 hls.js가 라이브 sliding window로 인식 → backward seek 차단.

**해결**: ffmpeg에 `-hls_playlist_type event` 추가.

```
#EXT-X-PLAYLIST-TYPE:EVENT   ← 이 한 줄이 m3u8에 박혀야 시크 가능
```

EVENT 타입은:
- 모든 segment를 timeline으로 유지 (sliding 안 함)
- hls.js가 전체 m3u8 길이를 seekable로 노출
- 새 segment는 끝에 append (라이브성 유지)

> 일반 가이드: `TROUBLESHOOTING.md` §3.3 "LIVE 버튼을 눌러도 라이브로 안 감"

---

## 4. CPU 100% 포화 (LOAD 7.8)

**증상**: 라이브 + HLS + RTSP 모두 동작하지만 LOAD 1분 평균 7.8 (4코어 정원 초과). SSH 응답성 저하.

**원인**: rpicam-vid가 H.264로 출력하는데 ffmpeg가 MJPEG 출력을 위해 **SW H.264 디코드 + SW MJPEG 인코드**를 720p15에 추가. 디코드만으로 한 코어 100%.

**해결**: 멀티보드 뷰어 호환을 위한 8080 MJPEG 출력을 제거. 라이브는 WebRTC가 담당하므로 멀티보드 뷰어 RPi 3B 패널은 검정으로 받아들임.

```python
# stream_server.py — MJPEG 출력 제거 후
ffmpeg [
    "-c:v copy -f hls ...",       # HLS (인코딩 0)
    "-c:v copy -f rtsp ..."       # RTSP push (인코딩 0)
]
```

결과: LOAD 7.8 → **1.8**.

---

## 5. WebRTC가 안 뜨고 HLS로 폴백

**증상**: 페이지 열면 ~5초 뒤 영상 표시 (WebRTC 0.2초가 아니라 HLS 지연 그대로).

**원인 1**: H.264 High profile은 일부 브라우저 WebRTC 디코더에서 지원 약함. Chrome/Firefox가 SDP answer를 거절하거나 video frame을 디코딩 못 함.

**해결 1**: rpicam-vid `--profile baseline`. Baseline / Constrained Baseline은 모든 WebRTC 클라이언트가 디코딩 가능.

**원인 2**: ICE candidate에 RPi의 LAN IP만 있고 Tailscale IP가 없음. 클라이언트(Tailscale)에서 LAN으로 못 도달.

**해결 2**: `mediamtx.yml`의 `webrtcAdditionalHosts: [<tailscale-ip>]` 설정. ICE 협상 시 Tailscale IP 100.x.x.x를 candidate로 광고.

---

## 6. "실시간으로" 누른 후 시크 시 00:01로 리셋

**증상**: 1분 시청 → 시크바 중간 → 시간이동 OK → "실시간으로" → LIVE 복귀 → **다시 시크 시 00:01에서 시작 (과거 영상 안 보임)**.

**원인**: 모드 전환 시 hls.js를 destroy/재생성. 두 번째 attach 때 hls.js가 m3u8을 다시 처음부터 로드 → currentTime이 0으로 리셋.

**해결**: video element를 **두 개로 분리**.
- `dvrVideo`: hls.js attach **유지** (페이지 로드 시 한 번만 만듦)
- `liveVideo`: WebRTC `srcObject`. 라이브 모드에 z-index로 위에 덮음

```html
<video id="dvrVideo"  controls></video>
<video id="liveVideo" class="live-overlay"></video>  <!-- z-index: 3 -->
```

모드 전환 = 단순히 `liveVideo` 보임/숨김 토글. hls.js의 currentTime / buffer는 영향 안 받음. 시크 위치 영구 보존.

부수: `enterLiveMode`가 `dvrVideo.currentTime = liveSyncPosition`을 set하면 seeking 이벤트가 자기 자신을 트리거 → `enterSeekMode` 무한 루프. **`suppressSeekOnce` 플래그**로 1회 무시.

---

## 진단에 결정적이었던 명령어 모음

```bash
# 1. .ts에 SPS/PPS 들어있는지
ffprobe -v error -show_entries stream=codec_name,profile,level seg_*.ts | head

# 2. m3u8에 EVENT 태그 있는지
grep PLAYLIST-TYPE /srv/dvr/dvr.m3u8

# 3. MediaMTX가 publisher 정상 받는지
journalctl -u mediamtx | grep "path cam"

# 4. WebRTC endpoint reachable
curl -s -o /dev/null -w "%{http_code}\n" http://<rpi>:8889/cam/whep   # 405 = OK

# 5. 인코더 가용 여부
ffmpeg -encoders 2>/dev/null | grep h264

# 6. 시스템 부하 추세
uptime    # 1m / 5m / 15m 평균. 4코어면 4.0 위는 위험
```

---

## 다음 빌드에서 같은 실수를 안 하려면

본 6건의 공통 패턴은 **레이어 경계의 가정이 틀린 경우**.

| Case | 잘못된 가정 |
|------|-------------|
| 1 | "두 프로세스가 동시에 카메라를 잡을 수 있다" |
| 2 | "ffmpeg HLS muxer가 알아서 SPS/PPS를 inject한다" |
| 3 | "EVENT 타입은 default라 명시 불필요" |
| 4 | "h.264 → MJPEG copy는 가벼울 것" (사실 SW 디코드 + SW 인코드 둘 다 발생) |
| 5 | "H.264 High profile = WebRTC 호환" / "MediaMTX가 외부 IP 자동 감지" |
| 6 | "토글 = 한 video element에서 srcObject↔src 교차" |

각 가정을 사전에 의심하고 ffprobe / journalctl / `ss -tlnp` 같은 **레이어 경계 확인 도구**를 일찍 쓰는 것이 시간 절약.
