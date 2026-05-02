# 하드웨어 가이드 — 무엇을 사야 하나?

이 프로젝트를 처음 시작할 때 필요한 부품과 선택 기준을 정리한 문서. 한국 쇼핑몰 위주로 작성했다.

---

## 1. 보드 비교 — RPi 3B / 4 / 5

| 항목 | RPi 3B (B+) | RPi 4 (4GB) | **RPi 5 (8GB)** |
|---|---|---|---|
| CPU | Cortex-A53 1.2GHz × 4 | Cortex-A72 1.5GHz × 4 | Cortex-A76 2.4GHz × 4 |
| RAM | 1 GB | 4 GB | 8 GB |
| H.264 HW 인코더 | ✓ (1080p30) | ✓ (1080p30) | **✕ (제거됨)** |
| H.264 SW 인코딩 | 720p가 한계 | 1080p30 가능 | 1080p60 여유 |
| 이더넷 | 100Mbps | 1Gbps | 1Gbps |
| 저장 확장 | microSD only | microSD + USB 3.0 | microSD + USB 3.0 + **PCIe NVMe** |
| 가격(2026) | ~3.5만원 | ~9만원 | ~15만원 (8GB) |
| 발열 | 낮음 (수동 가능) | 중간 | 높음 (액티브 쿨러 필수) |

### 본 프로젝트 추천

| 시나리오 | 추천 보드 | 비고 |
|---|---|---|
| **이미 RPi 3B 있음, 빨리 시작** | RPi 3B | 720p / 4시간 보존 / 표준 HLS |
| **신규 구매, 균형형** | **RPi 5 (4GB)** | 1080p30 / 24시간+ / LL-HLS 권장 |
| **NVR 수준 풀스펙** | RPi 5 (8GB) + NVMe HAT | 듀얼 카메라 / 수 주 보존 / AI까지 |

> RPi 4도 잘 동작하지만 **이미 시장 가격이 RPi 5와 비슷**하므로 신규 구매라면 RPi 5가 이득이다.

---

## 2. 카메라 모듈 비교

라즈베리파이용 카메라는 크게 4종이 흔하게 쓰인다.

| 모델 | 센서 | 해상도 | 야간 | 가격 | 비고 |
|---|---|---|---|---|---|
| **Camera Module v2** | IMX219 | 8MP, 1080p30 | 약함 | ~3.5만원 | **본 프로젝트 기본** |
| Camera Module v3 | IMX708 | 12MP, 1080p50 | 보통 (오토포커스) | ~5만원 | RPi 5 권장 |
| Camera Module v3 NoIR | IMX708 | 12MP | **IR 가능** | ~5만원 | 적외선 LED 조합 시 야간 가능 |
| **HQ Camera** | IMX477 | 12MP, C/CS 마운트 | 좋음 (큰 센서) | ~9만원 | 외장 렌즈 필요 |
| Global Shutter Camera | IMX296 | 1.6MP | — | ~6만원 | 산업용 (모션 블러 X) |
| Pi AI Camera | IMX500 | 12MP + AI | — | ~10만원 | 센서 내장 NPU |
| USB 웹캠 (Logitech 등) | 다양 | 보통 720p~1080p | 보통 | 2~5만원 | 가장 호환성 좋음 |

### IMX219 (본 프로젝트 기본)
- 가성비 최고
- 1280×720 ~ 1920×1080 영역에서 H.264 HW 인코더와 잘 맞음
- **저조도에서 노이즈가 큼** → 옥외 24시간 운용은 어려움 (필요하면 NoIR + IR LED)

### CSI 케이블 주의
- RPi 3B/4 ↔ Camera v2: **표준 CSI 15핀**
- RPi 5: **얇은 CSI** (다른 폼팩터, 어댑터 필요할 수 있음)
- 케이블 손상 시 진단 가이드: 보드 통합 [`멀티보드-뷰어-진단-가이드`](#)

---

## 3. SD카드 — 가장 자주 망가지는 부품

### 3.1 일반 vs 고내구

| 등급 | 표시 | TBW (총 쓰기량) | 1Mbps 24/7 시 수명 |
|---|---|---|---|
| 일반 (Class 10) | ![](https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/SD-Memory-Card-Logo.svg) | ~10 TB | **약 3년** |
| **High Endurance** | "Endurance" 라벨 | 100~200 TB | 30~60년 |
| **Pro Endurance** | "PRO Endurance" | 200~500 TB | 60~150년 |
| MAX Endurance | SanDisk MAX 라벨 | 800 TB | 250년+ |

24시간 영상 녹화는 **SD카드를 가장 빨리 마모시키는 워크로드**다. 일반 카드를 쓰면 1~2년 안에 망가질 가능성이 높다. **반드시 Endurance 등급으로**.

### 3.2 추천 모델 (한국 구매 가능)

| 모델 | 용량 | 가격대(2026) | 한 줄 평 |
|---|---|---|---|
| Samsung PRO Endurance | 64/128/256 GB | 1.5~4만 | 가장 무난, 쿠팡 즉배 |
| SanDisk High Endurance | 64/128 GB | 1.5~3만 | 검증된 NVR 표준 |
| **SanDisk MAX Endurance** | 128/256 GB | 3.5~7만 | 24/7 운용 시 1순위 |
| Lexar HighEndurance | 64/128 GB | 1.2~2.5만 | 가성비 |

> "이름이 같아 보이는 가짜 카드"가 한국 쇼핑몰에 흔하다. **Samsung 정품 인증 마크**, **SanDisk 정품 시리얼 확인**(www.sandisk.com/wugs)을 꼭 거치자.

### 3.3 용량 계산 (보존 시간별)

| 해상도 / 비트레이트 | 4시간 | 24시간 | 7일 | 30일 |
|---|---|---|---|---|
| 720p / 1.0 Mbps | 1.8 GB | 11 GB | 76 GB | 324 GB |
| 720p / 1.5 Mbps | 2.7 GB | 16 GB | 113 GB | 486 GB |
| 1080p / 2.0 Mbps | 3.6 GB | 22 GB | 151 GB | 648 GB |
| 1080p / 3.0 Mbps | 5.4 GB | 32 GB | 226 GB | 972 GB |

> 디스크 사용은 보존 시간 × 비트레이트 × 1.05 (썸네일 +5%) 정도로 가산.

---

## 4. SSD 옵션 — 진심으로 가려면

### 4.1 USB 3.0 SSD (RPi 4 / 5)

- USB 3.0 외장 SSD를 그대로 마운트하면 SD카드 마모 걱정 끝
- **부팅까지 SSD에서**: RPi 4/5는 USB 부팅 지원 (Imager에서 부트로더 모드로 설정)
- 추천: Samsung T7, Crucial X8, SanDisk Extreme Portable SSD
- 1TB 기준 12~15만원

### 4.2 NVMe HAT (RPi 5 전용)

- RPi 5는 **PCIe x1 슬롯**이 있어 NVMe SSD를 직접 연결 가능
- **공식 M.2 HAT+** (Pimoroni / Pineberry / Geekworm 등 판매)
- 5~10만원 + NVMe SSD (1TB ~12만)
- 속도/지연 모두 USB 대비 우수, 케이스 컴팩트

### 4.3 한국 NVMe HAT 구매 경로

- 디바이스마트, 엘레파츠에 **Pimoroni NVMe Base** 입고 가끔 있음
- 알리익스프레스 / 쿠팡 글로벌에서 Geekworm 모델이 가장 흔함
- 호환 SSD 리스트: https://pip.raspberrypi.com/categories/685-whitepapers-app-notes (Pi 5 NVMe 호환성)

---

## 5. 쿨링 — RPi 5에서는 거의 필수

### 5.1 RPi 3B
- 720p HW 인코딩이라 발열 적음
- **방열판 한 장**이면 충분
- 케이스에 포함되는 경우 많음

### 5.2 RPi 5
- A76 SW 인코딩 + ffmpeg + nginx 동시 → 80℃ 도달 가능
- 80℃ 넘으면 자동 throttle → 영상 품질 흔들림
- **Active Cooler (공식)** 가 가장 안정적 (~1만원)
- 알루미늄 케이스 + 팬 일체형도 좋음

### 5.3 진단 명령
```bash
vcgencmd measure_temp        # 현재 SoC 온도
vcgencmd get_throttled       # throttle 발생 여부 (0x0 = 정상)
```

---

## 6. 케이스 / POE / UPS

### 케이스
- 단일 보드 운용이면 **공식 RPi 5 케이스** + Active Cooler 통합형이 깔끔
- 옥외/벽면이면 IP65 등급 산업용 알루미늄 케이스 (디바이스마트 기준 4~8만)

### POE (Power over Ethernet)
- 카메라를 천장/외부에 둘 때 전원선 추가가 어려우면 POE HAT 사용
- RPi 4/5 공식 POE+ HAT: ~3.5만
- POE 스위치/인젝터 별도 (스위치가 없다면 인젝터 ~3만)

### UPS
- 정전 시 .ts 깨짐 방지
- RPi UPS HAT (Geekworm X728 등): 4~7만
- 또는 외부 미니 UPS (네트워크 장비용): 5~10만

---

## 7. 한국 쇼핑몰 가이드

| 쇼핑몰 | URL | 강점 |
|---|---|---|
| **쿠팡** | https://www.coupang.com | 즉시 배송, SD카드/케이스 빠름 |
| **디바이스마트** | https://www.devicemart.co.kr | 라즈베리파이 정식, HAT/카메라 다양 |
| **엘레파츠** | https://www.eleparts.co.kr | 디바이스마트와 비슷한 카테고리 |
| **메카솔루션** | https://mechasolution.com | 메이커용, 액세서리 풍부 |
| **아이씨114(IC114)** | https://www.ic114.com | 라즈베리파이 정식 수입 |
| **알리익스프레스** | https://aliexpress.com | NVMe HAT, 저렴한 액세서리 |
| **쿠팡 글로벌(로켓직구)** | — | 알리보다 빠른 해외 부품 |

> 라즈베리파이 본체는 **정식 수입사(IC114, 디바이스마트, 엘레파츠 등)** 에서 사는 것을 권장. 알리/유사몰에는 위조 보드가 있다.

---

## 8. 추천 구성 3가지

### A. 예산형 — "있는 거 활용" (~5~7만 추가)

| 부품 | 모델 | 가격 |
|---|---|---|
| RPi 3B (이미 있음 가정) | — | 0 |
| Camera v2 (IMX219) | 정품 | 3.5만 |
| **High Endurance microSD 64GB** | SanDisk Endurance | 2만 |
| 방열판 + 케이스 | 임의 | 1만 |
| (옵션) 5V 3A 전원 | 정품 | 1.5만 |
| **합계** | | **~5~8만** |

→ 720p / 4시간 보존 / 표준 HLS

### B. 균형형 — "신규 구매, RPi 5 권장" (~30만)

| 부품 | 모델 | 가격 |
|---|---|---|
| **RPi 5 (4GB)** | 정품 | 11만 |
| Active Cooler | 정품 | 1만 |
| Camera v2 (IMX219) 또는 v3 | 정품 | 3.5~5만 |
| **PRO Endurance microSD 256GB** | Samsung | 4.5만 |
| 정품 27W USB-C 전원 | 정품 | 2.5만 |
| 케이스 (액티브 쿨러 호환) | 임의 | 2만 |
| **합계** | | **~25~30만** |

→ 1080p30 / 24시간 보존 / LL-HLS

### C. 풀스펙 NVR — "수 주 보존 + AI" (~50~80만)

| 부품 | 모델 | 가격 |
|---|---|---|
| RPi 5 (8GB) | 정품 | 15만 |
| Active Cooler | 정품 | 1만 |
| **NVMe HAT** (Pimoroni 등) | — | 5~8만 |
| **NVMe SSD 1TB** | Samsung 980 / WD Black SN770 | 12만 |
| Camera v2 × 2 또는 HQ Camera × 1 | — | 7~9만 |
| 정품 27W USB-C 전원 | 정품 | 2.5만 |
| 케이스 (HAT 호환) | 알루미늄 | 4만 |
| (옵션) POE+ HAT + 스위치 | — | 7만 |
| (옵션) UPS HAT | Geekworm X728 | 6만 |
| **합계** | | **~50~80만** |

→ 1080p30 LL-HLS / 1주~수 주 보존 / 듀얼 카메라 / 정전 대비

---

## 9. 체크리스트 — 박스 까기 전에

- [ ] 본체 보드 (RPi 3B 또는 5)
- [ ] 정품 USB-C 전원 (RPi 5는 27W 권장, 일반 5V 3A로는 부족)
- [ ] 카메라 모듈 + **호환 CSI 케이블** (RPi 5는 얇은 케이블)
- [ ] microSD 카드 (Endurance 등급)
- [ ] microSD 리더기 (PC에서 OS 굽기용)
- [ ] HDMI 케이블 (초기 설정 시 모니터 연결용, 또는 Headless로 SSH만)
- [ ] 키보드/마우스 (Headless면 생략 가능)
- [ ] 이더넷 케이블 (Wi-Fi 보다 안정적, NVR 용도면 필수)
- [ ] 방열판 또는 액티브 쿨러
- [ ] 케이스
- [ ] (선택) USB SSD 또는 NVMe HAT + SSD

---

## 10. 자주 받는 하드웨어 질문

**Q. RPi Zero 2W로도 가능한가?**
→ 720p HW 인코딩은 되지만 RAM 512MB 한계로 ffmpeg + nginx 동시 운용은 빠듯. 시도는 가능하지만 권장 안 함.

**Q. RPi 4도 좋다고 들었는데?**
→ 매우 좋음. 사실 LL-HLS까지 1080p로 잘 돌아간다. 다만 가격 차이가 RPi 5와 5~6만원 정도라 신규라면 RPi 5가 이득.

**Q. 카메라가 2~3대 동시에 필요한데?**
→ RPi 5는 CSI 슬롯 2개라 듀얼 카메라 가능. 3대 이상이면 USB 웹캠 추가 또는 보드 분산(여러 RPi).

**Q. 야간 촬영도 되나?**
→ IMX219는 약함. NoIR 버전 + IR LED 보드 추가 또는 HQ Camera + 야간 렌즈 권장. 별도 IR LED 모듈은 알리에서 5천원~.

**Q. 보드 발열 너무 심함**
→ `vcgencmd measure_temp`로 확인. 70℃ 넘으면 액티브 쿨러 추가. 케이스 환기 구멍 막혀 있는 경우도 의심.

**Q. SD카드 잘못 사면 얼마나 차이 나나?**
→ 일반 카드는 24/7 녹화 시 1~2년에 망가짐. Endurance 카드는 30년+. 가격 차이는 1~2만원이라 무조건 Endurance.

---

다음 → [`SETUP-GUIDE.md`](SETUP-GUIDE.md) (단계별 설치 매뉴얼)
