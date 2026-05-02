# 핵심 개념 가이드

이 프로젝트가 어떻게 동작하는지를 **처음 보는 사람도 따라올 수 있도록** 정리한 문서. 코드보다는 "왜 이렇게 만드는가"에 집중한다.

---

## 1. 라이브 스트리밍 한눈에 보기

영상이 카메라에서 휴대폰까지 가는 길은 크게 4단계다.

```
[1] 캡처      → 센서에서 픽셀(raw 프레임)을 읽음
[2] 인코딩    → H.264/H.265 같은 코덱으로 압축
[3] 패키징    → 네트워크로 보내기 좋게 작은 조각으로 나눔
[4] 전달/재생 → 서버가 조각을 보내고, 플레이어가 이어붙여 재생
```

이 프로젝트의 핵심은 **[3] 패키징을 SD카드에 동시에 저장**해서 "지난 영상도 이어붙여 재생"이 가능하게 만드는 것이다. 그래서 라이브 + 시크백이 같은 메커니즘으로 처리된다.

---

## 2. 프로토콜 비교 — 왜 HLS인가?

라이브 영상 전송 방식은 여러 가지가 있고, 각각 장단점이 있다.

| 프로토콜 | 지연 | DVR(시크백) | 모바일 호환 | 방화벽 통과 | 본 프로젝트 적합도 |
|---|---|---|---|---|---|
| **RTSP** | ~200ms | ✕ (별도 녹화 필요) | △ (브라우저 X) | △ | ✕ |
| **RTMP** | ~2s | ✕ | △ (Flash 의존, 사실상 폐기) | ○ | ✕ |
| **HLS** (이 프로젝트) | 6~10s | **✓ 자연스럽게** | ✓ (Safari 네이티브) | ◎ (HTTP) | **◎** |
| **LL-HLS** | 1~3s | ✓ | ✓ | ◎ | ◎ (RPi 5 권장) |
| **MPEG-DASH** | 6~10s | ✓ | △ (iOS 약함) | ◎ | ○ |
| **WebRTC** | <500ms | ✕ (실시간만) | ◎ | △ (UDP) | ✕ |

**HLS를 고른 이유**:
1. **HTTP 위에서 동작** → Tailscale, 일반 웹서버, CDN 등 그대로 사용 가능
2. **DVR이 자연스러움** → 플레이리스트(`.m3u8`)에 모든 과거 세그먼트를 그대로 유지하면 끝
3. **iOS Safari 네이티브 지원** → 설치 없이 모든 휴대폰에서 재생
4. **`ffmpeg`의 표준 muxer** 가 있어 추가 의존성 없음

지연이 좀 큰 게 단점인데, 보안/모니터링 용도로는 6~10초 지연이 큰 문제가 아니다. 정 짧게 가야 하면 LL-HLS로 1~3초까지 줄일 수 있다.

---

## 3. HLS는 어떻게 동작하나?

HLS는 영상을 **작은 조각(.ts)** 으로 나누고, **플레이리스트(.m3u8)** 에 그 조각들의 목록을 적어 둔 다음, **HTTP**로 둘 다 서빙하는 방식이다.

### 3.1 파일 구조

```
/srv/dvr/
├── dvr.m3u8          ← 플레이리스트 (텍스트, 조각 목록)
├── seg_00001.ts      ← 영상 조각 1 (2초)
├── seg_00002.ts      ← 영상 조각 2 (2초)
├── seg_00003.ts      ← ...
└── seg_NNNNN.ts      ← 가장 최신 조각
```

### 3.2 플레이리스트(.m3u8) 예시

```m3u
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PROGRAM-DATE-TIME:2026-05-02T14:00:00.000+09:00
#EXTINF:2.000000,
seg_00001.ts
#EXTINF:2.000000,
seg_00002.ts
#EXTINF:2.000000,
seg_00003.ts
... (계속 추가됨)
```

- `#EXTINF:2.000000,` → 다음 조각은 2초짜리
- `#EXT-X-PROGRAM-DATE-TIME` → 그 조각이 **언제(절대 시각)** 녹화됐는지
- 새 조각이 만들어질 때마다 ffmpeg가 m3u8 끝에 줄을 추가

### 3.3 플레이어가 하는 일

1. `dvr.m3u8` 다운로드 (텍스트 파일, 작음)
2. 목록을 보고 가장 최신 조각 몇 개를 다운로드 → 라이브 재생 시작
3. 일정 주기로 m3u8를 다시 받아 새 조각이 추가됐는지 확인
4. 사용자가 시크바를 옮기면 → 그 시각의 조각으로 점프해서 재생

> 즉 **DVR도 라이브도 메커니즘이 같다.** 목록의 어디를 재생하느냐의 차이일 뿐.

---

## 4. DVR(타임머신)은 어떻게 가능한가?

일반적인 라이브 HLS는 **최근 N개 조각만 플레이리스트에 남기고 옛 조각은 삭제**한다 (`hls_list_size 6` 같은 옵션). 그래서 시크백이 안 된다.

이 프로젝트의 트릭은 단순하다:

```bash
-hls_list_size 0
```

`0`은 "**플레이리스트에 모든 조각을 다 남겨라**" 라는 뜻이다. 그러면:

- 플레이리스트가 시간이 갈수록 길어지고
- 그 길이만큼 시크 가능 범위(=**DVR window**)가 늘어난다.

```
방송 시작 → 1시간 후 → 2시간 후 → ... → 현재(LIVE)
[========================시크바 가능 범위=======================]
                                                              ▲ liveSyncPosition
```

다만 무한정 쌓으면 SD카드가 가득 차므로, 별도 cron으로 **보존 시간(예: 4시간)을 넘긴 조각은 파일과 m3u8에서 모두 삭제**한다 (`docs/IMPLEMENTATION-PLAN.md` §5.3).

### 왜 `delete_segments` 플래그를 안 쓰나?

ffmpeg에 `delete_segments` 플래그가 있긴 하지만, 그건 `hls_list_size`가 정한 개수 기준으로만 동작해서 **DVR window 자체를 줄여 버린다**. 우리는 "플레이리스트는 길게 유지하면서, 보존 시간만큼만 디스크에 두고 싶다" 이므로 cron 정리 방식을 쓴다.

---

## 5. LL-HLS — 저지연 확장

표준 HLS는 조각 하나가 통째로 만들어져야 플레이리스트에 추가된다. 그래서 조각 길이(예: 2초) × 버퍼(보통 3개) = **6~10초 지연**이 기본이다.

**LL-HLS**는 Apple이 2019~2020년에 표준화한 확장으로, 조각을 **부분(part, 200ms 단위)** 으로 쪼개고 플레이리스트에 부분 단위로 추가한다.

```
표준 HLS: [────세그먼트 2s────][────세그먼트 2s────]
                         ↑ 여기서 비로소 추가됨

LL-HLS:   [p][p][p][p][p][p][p][p][p][p]
           ↑  ↑  ↑  ↑  ↑  ... 매 200ms 추가
```

iOS Safari 14+, hls.js 1.x가 지원한다. 라이브 지연이 **1~3초**까지 줄어들지만, RPi 3B의 HW 인코더는 LL-HLS 친화적이지 않으므로 **RPi 5 + libx264 SW 인코딩** 조합에서 추천한다.

자세한 사양: https://datatracker.ietf.org/doc/html/rfc8216bis (HLS 2nd ed., LL-HLS 포함)

---

## 6. 썸네일 호버 — WebVTT 트랙

치지직/유튜브에서 시크바에 마우스를 올리면 그 시점의 썸네일이 뜨는 기능. 이 동작은 **WebVTT thumbnail track** 이라는 비공식 표준으로 구현된다.

### 6.1 동작 원리

1. ffmpeg가 영상에서 **10초마다 1장씩** 작은 JPG를 추출
2. ImageMagick `montage`로 100장씩 묶어 **스프라이트 시트** 생성 (네트워크 요청 줄이기 위해)
3. **`thumbs.vtt`** 파일에 "이 시각엔 이 스프라이트의 이 좌표를 봐라"고 매핑
4. 플레이어(Plyr)가 이걸 읽어서 호버 시 해당 영역만 잘라 보여줌

### 6.2 thumbs.vtt 예시

```
WEBVTT

00:00:00.000 --> 00:00:10.000
sprite_0001.jpg#xywh=0,0,160,90

00:00:10.000 --> 00:00:20.000
sprite_0001.jpg#xywh=160,0,160,90

00:00:20.000 --> 00:00:30.000
sprite_0001.jpg#xywh=320,0,160,90
...
```

`xywh=x,y,w,h`는 "해당 스프라이트 이미지에서 (x,y) 위치의 w×h 영역을 잘라 써라"는 뜻이다. 표준은 https://www.w3.org/TR/webvtt1/ 에 있고, 썸네일 트랙은 거의 모든 상용 플레이어(JW Player, Bitmovin, Twitch, Mux 등)가 같은 형식을 쓴다.

---

## 7. 라즈베리파이 카메라 스택

라즈베리파이에서 카메라 영상을 받는 방법은 시기별로 변해 왔다.

| 시대 | 도구 | 비고 |
|---|---|---|
| Bullseye 이전 | `raspivid`, `raspistill` | **deprecated** — 더 이상 권장 안 됨 |
| Bullseye 이후 | **`libcamera-vid`**, `libcamera-still` | 본 프로젝트가 사용 |
| 파이썬 | **`picamera2`** | libcamera 위의 파이썬 바인딩 |
| 저수준 | `v4l2-ctl`, `/dev/video0` | 일반 V4L2 디바이스로도 접근 가능 |

`libcamera-vid`는 H.264 HW 인코더(VideoCore IV/VI)에 직접 접근해서 **CPU 거의 안 쓰고 1080p30 H.264 출력**이 가능하다. 단, **RPi 5는 HW H.264 인코더가 빠졌다** — 그래서 RPi 5에서는 raw YUV로 받아서 `ffmpeg + libx264`로 SW 인코딩한다 (`docs/IMPLEMENTATION-PLAN.md` §4.1).

공식 문서: https://www.raspberrypi.com/documentation/computers/camera_software.html
libcamera 자체: https://libcamera.org/

---

## 8. ffmpeg HLS muxer가 하는 일

ffmpeg는 우리가 **단 한 줄로** "H.264 입력을 받아 → 2초 단위로 잘라 → .ts 파일과 .m3u8을 만들어라"라고 시킬 수 있게 해주는 도구다.

```bash
ffmpeg -i (입력) -c:v copy -f hls -hls_time 2 -hls_list_size 0 ... (출력).m3u8
```

- `-c:v copy` → **재인코딩 안 함** (libcamera-vid가 이미 H.264로 줬으니까). CPU 거의 안 쓴다.
- `-f hls` → 출력 포맷을 HLS muxer로
- 나머지 옵션은 §4.2에서 설명

대안 도구도 있다:
- **MediaMTX** — RTSP 입력을 받아 자동으로 HLS/WebRTC로 변환해 주는 만능 서버. 빠르게 구성하기 좋음
- **nginx-rtmp-module** — RTMP 입력을 HLS로 트랜스먹싱. 옛날 방식
- **GStreamer** `hlssink2` — ffmpeg 대신 쓸 수 있음

ffmpeg를 고른 이유는 **세밀한 옵션 제어**(LL-HLS, programDateTime 등)와 **재시작 시 append 동작**이 안정적이기 때문이다.

---

## 9. "시크바 끝까지 끌기" 시퀀스

사용자가 휴대폰 시크바를 왼쪽 끝(=4시간 전)으로 끄는 순간 어떤 일이 일어나는지 단계별로:

```
[휴대폰] 사용자가 seek bar 끌기
      ↓
[hls.js] 현재 .m3u8에서 4시간 전에 해당하는 .ts를 찾음
      ↓
[hls.js] 해당 .ts의 URL을 GET 요청 → nginx → SD카드 → 응답
      ↓
[hls.js] 받은 .ts를 MSE(Media Source Extensions) 버퍼에 push
      ↓
[<video>] 새 위치부터 재생
      ↓
[hls.js] 그 다음 .ts들도 미리 가져와서 끊기지 않게 버퍼링
```

여기서 핵심은 **HLS는 순수 HTTP**라서 시크백이 "특정 .ts 파일을 GET 하는 행위"로 자연스럽게 환원된다는 점. 별도 시크 프로토콜 같은 게 없다. 그냥 다른 파일을 받을 뿐이다.

---

## 10. 자주 헷갈리는 용어 정리

| 용어 | 뜻 | 비고 |
|---|---|---|
| **세그먼트** | HLS에서 하나의 .ts 또는 .m4s 파일 | 보통 2~6초 길이 |
| **플레이리스트** | 세그먼트 목록 (.m3u8) | 두 종류: media playlist / master playlist |
| **DVR window** | 시크 가능한 시간 범위 | 우리 프로젝트는 보존 시간 = DVR window |
| **liveSyncPosition** | hls.js가 "이쯤이 라이브의 가장 끝"이라고 판단하는 위치 | LIVE 버튼이 여기로 점프 |
| **LL-HLS** | Low-Latency HLS | parts 단위 200ms 푸시 |
| **CMAF** | Common Media Application Format | DASH/HLS 양쪽에서 같은 .m4s 쓰는 표준 |
| **MSE** | Media Source Extensions | 브라우저가 자바스크립트로 비디오 버퍼를 직접 채우는 W3C API |
| **VTT (WebVTT)** | Web Video Text Tracks | 자막 + 챕터 + 썸네일 트랙 표준 |
| **TS (MPEG-TS)** | MPEG Transport Stream | HLS 기본 컨테이너 (.ts) |
| **fMP4 / CMAF** | fragmented MP4 | LL-HLS 권장 컨테이너 (.m4s) |
| **muxer** | 영상/음성/자막을 하나의 컨테이너로 묶는 것 | demuxer는 그 반대 |
| **codec** | 영상 데이터를 압축/풀어내는 알고리즘 | H.264, H.265, AV1 등 |
| **GOP** | Group of Pictures (키프레임 간 거리) | HLS 세그먼트 길이의 배수가 보통 GOP |
| **keyframe / IDR** | 다른 프레임 의존 없이 디코딩 가능한 프레임 | 시크 정확도의 기준 |
| **bitrate** | 초당 데이터량 (bits per second) | 1Mbps = 1,000,000 bps |
| **ABR** | Adaptive Bitrate | 네트워크 따라 화질 자동 변경 |

---

## 더 깊이 들어가려면

- **RFC 8216** (HLS 1차 사양): https://datatracker.ietf.org/doc/html/rfc8216
- **HLS 2nd Edition Draft** (LL-HLS 포함): https://datatracker.ietf.org/doc/html/draft-pantos-hls-rfc8216bis
- **Apple HLS 포털**: https://developer.apple.com/streaming/
- **hls.js API 문서**: https://github.com/video-dev/hls.js/blob/master/docs/API.md
- **Mux 블로그 — HLS 시리즈**: https://www.mux.com/blog (검색: HLS, LL-HLS)

다음으로 → [`HARDWARE.md`](HARDWARE.md) (실제 부품 선택) → [`SETUP-GUIDE.md`](SETUP-GUIDE.md) (단계별 설치)
