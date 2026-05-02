# RPi Camera DVR

라즈베리파이 IP카메라(IMX219 / Pi Camera Module)에 **치지직 / 트위치 / 유튜브 라이브 수준의 DVR(타임머신) 재생** 기능을 추가하는 프로젝트.

휴대폰으로 라이브를 보다가 시크바를 왼쪽으로 끌면 방송 시작 시점(또는 최근 N시간)까지 되돌려 볼 수 있고, 호버 시 썸네일 미리보기, **"실시간"** 버튼 한 번이면 라이브로 복귀 — 즉 치지직과 동일한 UX를 라즈베리파이 한 대로, SD카드 저장 기반으로 구현.

```
[IMX219] → [RPi] → ffmpeg HLS muxer → SD카드 (.ts 세그먼트 + 썸네일)
                          │
                          ▼
                       nginx (:8090)
                          │
                          ▼
                휴대폰 (hls.js + Plyr, Tailscale 경유)
```

## 진행 상태

**2026-05-02 — 기획 단계.** 사양과 로드맵 작성 완료. 구현 착수 전.

상세 내용은 **[docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md)** 참고: 시스템 아키텍처, RPi 3B(HW H.264) / RPi 5(SW libx264) 별 ffmpeg 파이프라인, LL-HLS 설정, WebVTT 썸네일 스프라이트 생성, SD카드 보존 정책, 6단계 로드맵, 그리고 표준 문서 + 학술 논문 레퍼런스(RFC 8216, Apple LL-HLS, hls.js / Plyr, HTTP adaptive streaming 서베이 등).

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

## 관련 프로젝트

이 프로젝트는 [Multi-Board-Viewer](https://github.com/squid55/Multi-Board-Viewer)의 자매 프로젝트로, 라즈베리파이 카메라 노드에 한정된 DVR 레이어를 추가합니다. 멀티보드 뷰어 없이 단독으로 동작합니다.

## 라이선스

미정.
