# RPi Camera DVR

라즈베리파이 IP카메라(IMX219 / Pi Camera Module)에 **치지직 / 트위치 / 유튜브 라이브 수준의 DVR(타임머신) 재생** 기능을 추가하는 프로젝트.

휴대폰으로 라이브를 보다가 시크바를 왼쪽으로 끌면 **방송 시작 시점(또는 최근 N시간)** 까지 되돌려 볼 수 있고, 호버 시 썸네일 미리보기, **"실시간"** 버튼 한 번이면 라이브로 복귀 — 즉 치지직과 동일한 UX를 라즈베리파이 한 대로, SD카드 저장 기반으로 구현.

```
[IMX219] → [RPi] → ffmpeg HLS muxer → SD카드 (.ts 세그먼트 + 썸네일)
                          │
                          ▼
                       nginx (:8090)
                          │
                          ▼
                휴대폰 (hls.js + Plyr, Tailscale 경유)
```

---

## 📚 문서 구조

처음 본다면 **순서대로 읽으면 자연스럽다**.

| # | 문서 | 무엇이 들어 있나 |
|---|---|---|
| 1 | **[CONCEPTS](docs/CONCEPTS.md)** | HLS / DVR / LL-HLS / WebVTT 등 **핵심 개념을 그림과 표로 설명**. 처음이라면 여기부터. |
| 2 | **[HARDWARE](docs/HARDWARE.md)** | 보드(3B/4/5) · 카메라 · SD카드 · SSD · 케이스 비교. 한국 쇼핑몰 + **추천 구성 3종(예산/균형/풀스펙)**. |
| 3 | **[SETUP-GUIDE](docs/SETUP-GUIDE.md)** | OS 굽기부터 폰에서 시크 동작 확인까지 **그대로 따라할 수 있는 14단계 매뉴얼**. 단계별 검증 명령 포함. |
| 4 | **[IMPLEMENTATION-PLAN](docs/IMPLEMENTATION-PLAN.md)** | 더 깊은 사양 · 6단계 로드맵 · 위험 매트릭스 · ffmpeg 옵션 상세. |
| 5 | **[TROUBLESHOOTING](docs/TROUBLESHOOTING.md)** | **빠른 5단계 진단** + 카테고리별 흔한 증상/해결 + FAQ + 진단 명령어 치트시트. |
| 6 | **[REFERENCES](docs/REFERENCES.md)** | 표준(RFC/W3C/Apple) · 도구 공식 문서 · 한국어 자료 · 비슷한 OSS NVR · **학술 논문 12편**. |

---

## 진행 상태

**2026-05-02 — 기획 단계.** 문서·설계·로드맵·레퍼런스 정리 완료. 구현 착수 전.

## 결정해야 할 사항

- [ ] 보드: RPi 3B(720p / 4시간 보존)로 시작 vs RPi 5(1080p / 24시간+) 도착 대기
- [ ] 보존 시간: 1시간 / 4시간 / 24시간 / 방송 시작부터 누적
- [ ] 녹화 트리거: ① 부팅 후 항상 녹화 / ② 휴대폰의 "방송 시작" 버튼
- [ ] 플레이어: hls.js + Plyr (기본 후보) / video.js / Shaka
- [ ] LL-HLS 적용 여부
- [ ] 저장 매체: SD only / SD + USB SSD or NVMe HAT
- [ ] 인증: Tailscale only / 별도 토큰

## 로드맵 요약

1. **MVP** — libcamera-vid → ffmpeg HLS → nginx → 정적 hls.js 페이지. 휴대폰에서 1시간 전 시크 동작.
2. **썸네일 호버** — WebVTT 스프라이트 트랙.
3. **보존 정책** — cron 정리, SD 사용량 모니터링.
4. **UX 마감** — LIVE 배지, 절대 시각, PWA 설치.
5. **(선택) AI 이벤트 마커** — Jetson Orin YOLOv8 → webhook → 시크바 마커.
6. **(선택) RPi 5 마이그레이션** — 1080p30 LL-HLS, NVMe HAT, 듀얼 IMX219.

상세는 [`docs/IMPLEMENTATION-PLAN.md`](docs/IMPLEMENTATION-PLAN.md) 참조.

---

## 빠른 시작 (TL;DR)

이미 라즈베리파이 OS 가 설치된 RPi 3B 가 있다면:

```bash
# 1. 의존성
sudo apt update && sudo apt install -y ffmpeg nginx

# 2. DVR 폴더
sudo mkdir -p /srv/dvr/player && sudo chown -R pi:pi /srv/dvr

# 3. ffmpeg HLS 파이프라인 (수동 1회 시도)
libcamera-vid -t 0 --width 1280 --height 720 --framerate 30 \
  --codec h264 --bitrate 1500000 --inline -o - | \
  ffmpeg -fflags nobuffer -i - -c:v copy -an \
    -f hls -hls_time 2 -hls_list_size 0 \
    -hls_flags independent_segments+program_date_time+append_list \
    -hls_segment_filename '/srv/dvr/seg_%05d.ts' /srv/dvr/dvr.m3u8
```

다른 SSH 세션에서 `/srv/dvr/dvr.m3u8` + `seg_*.ts` 가 쌓이는지 확인. 그 다음은 [`SETUP-GUIDE.md`](docs/SETUP-GUIDE.md) 7~10단계(systemd / nginx / 폰 플레이어 / Tailscale)로.

---

## 관련 프로젝트

이 프로젝트는 [Multi-Board-Viewer](https://github.com/squid55/Multi-Board-Viewer)의 자매 프로젝트로, 라즈베리파이 카메라 노드에 한정된 DVR 레이어를 추가합니다. 멀티보드 뷰어 없이 단독으로 동작합니다.

비슷한 컨셉의 OSS NVR 들과의 비교/참고 코드는 [`REFERENCES.md` §5](docs/REFERENCES.md) 참조 (Frigate, MotionEye, ZoneMinder, picam, OvenMediaEngine 등).

---

## 라이선스

미정.
