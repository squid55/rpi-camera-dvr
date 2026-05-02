# Architecture

## 데이터 흐름

```
IMX219 (MIPI CSI) ─► rpicam-vid (H.264 baseline, --inline, 2s GOP)
                          │
                          ▼ stdout
                       ffmpeg
   ┌──────────────────────┼────────────────────────────┐
   │                      │                            │
   ▼ HLS muxer            ▼ RTSP push (TCP)            │
   /srv/dvr/seg_*.ts      rtsp://localhost:8554/cam    │
   /srv/dvr/dvr.m3u8           │                       │
        │                      ▼                       │
        │                 MediaMTX                     │
        │                      │                       │
        │                      ▼ WebRTC (UDP/SRTP)     │
        ▼                  :8889/cam/whep              │
   nginx :8090                  │                      │
        │                       │                      │
        ▼                       ▼                      │
        Tailscale (직접 P2P, 100.x.x.x)                │
        │                       │                      │
        ▼                       ▼                      │
   브라우저 dvrVideo (hls.js)  브라우저 liveVideo (RTCPeerConnection)
```

## 컴포넌트별 책임

### 1. rpicam-vid
- **역할**: 카메라 raw → H.264 인코딩 (RPi 3B HW 인코더 v4l2m2m)
- **출력**: stdout으로 H.264 elementary stream (annex B, inline SPS/PPS)
- **핵심 옵션**:
  - `--profile baseline` — WebRTC 브라우저 호환
  - `--inline` — 매 keyframe 앞에 SPS/PPS 삽입 (HLS 세그먼트 호환의 결정타)
  - `--intra 30` — 30프레임마다 keyframe = hls_time 2초와 정확히 일치
  - `--bitrate 1000000` — 1Mbps, 720p15에 충분

### 2. ffmpeg
- **역할**: H.264 demux → 두 출력으로 fan-out (인코딩 X)
- **출력 1: HLS DVR**
  - `-c:v copy` (재인코딩 없음)
  - `-hls_time 2` + `-hls_list_size 0` (sliding 없음, 모든 segment 유지)
  - `-hls_playlist_type event` (브라우저가 전체 timeline을 seekable로 인식)
  - `-hls_flags independent_segments+program_date_time+append_list`
  - `-strftime 1 -hls_segment_filename seg_%Y%m%dT%H%M%S.ts` — 절대시각 파일명, restart 시 충돌 없음
- **출력 2: RTSP push**
  - `-c:v copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/cam`
  - 같은 H.264 stream을 MediaMTX에 publish

### 3. MediaMTX
- **역할**: RTSP ingest → WebRTC publish (인코딩 0, 패킷 wrapping만)
- **포트**: 8554(RTSP), 8889(WebRTC HTTP), 8189(UDP/ICE)
- **WebRTC endpoint**: `POST http://host:8889/cam/whep` (WHEP 표준)
- **ICE**: STUN/TURN 비활성, `webrtcAdditionalHosts: [<tailscale-ip>]`로 직접 advertise

### 4. nginx
- **역할**: 정적 파일 서빙 (m3u8, .ts, player HTML)
- **포트**: 8090
- **MIME**: `application/vnd.apple.mpegurl m3u8`, `video/mp2t ts`
- **Cache-Control: no-cache** — m3u8가 매 2초 갱신되므로 필수

### 5. cron + 스크립트
- **`dvr-cleanup.sh`**: 4시간 넘은 `seg_*.ts` 삭제
- **`trim_m3u8.py`**: m3u8에서 사라진 segment entry 제거 (파일 소실 ↔ playlist 동기화)
- **주기**: 매 10분

### 6. player (브라우저)
- **video element 두 개를 z-index로 겹침**:
  - `dvrVideo` (controls 보유, hls.js attached, **항상 재생 유지**)
  - `liveVideo` (overlay, WebRTC `srcObject`, pointer-events: none)
- **토글 휴리스틱**:
  - 사용자가 progress bar 만지거나 일시정지 → liveVideo 숨김 (시크 모드)
  - 라이브 위치 ±3초 시크는 모드 전환 안 함 (자기 자신 트리거 회피)
  - "실시간으로" 버튼 → liveVideo 다시 표시 + dvrVideo를 `liveSyncPosition`으로 점프
- **`suppressSeekOnce` 플래그**: 모드 전환 시 자기가 트리거한 seeking 1회 무시

## 왜 video를 두 개 쓰는가

**한 video element + srcObject↔src 토글 시도 → 시크 위치 리셋 버그**:
- 시크 모드 진입할 때 hls.js를 새로 만듦 → m3u8을 처음부터 로드 → 두 번째 시크 시 currentTime 0:01로 리셋

**해결**: hls.js를 한 번만 만들고 평생 유지. WebRTC는 별도 video에 srcObject로 띄워 위에 덮음. 시크 모드 = 위 video를 숨기기만 → hls.js의 currentTime, buffer가 그대로 유지.

비용: 클라이언트가 HLS와 WebRTC stream 둘 다 동시 수신 → 클라이언트 CPU 약간 증가, 네트워크 추가. RPi 부담은 거의 없음(단순 fan-out).

## 시간이동 동작

- ffmpeg가 `EXT-X-PROGRAM-DATE-TIME` 태그를 매 segment에 박음
- player 시계 표시: 시크 모드일 때 `frag.programDateTime + (currentTime - frag.start) * 1000`로 절대시각 계산
- `EXT-X-PLAYLIST-TYPE:EVENT`라 hls.js가 전체 m3u8을 seekable timeline으로 인식

## 보안/접근

- 모든 트래픽은 Tailscale 100.x.x.x. 외부 인증 없음 (Tailscale ACL이 곧 인증)
- Tailscale 미가입 단말은 RPi에 접근 불가
- 추가 인증(JWT 등)이 필요하면 nginx 8090 / MediaMTX 8889 양쪽에 적용

## 자원 사용

| 항목 | 측정값 |
|------|--------|
| RPi 3B LOAD (4코어, 운영 중) | ~1.8 |
| RAM | ~470 MB / 906 MB |
| SD 사용 (4시간 보존) | ~1.8 GB / 9.7 GB 여유 |
| 클라이언트 1명 대역 (라이브+DVR 둘 다 fetch) | ~2 Mbps |
