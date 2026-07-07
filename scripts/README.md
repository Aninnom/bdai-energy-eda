# EDA 재현 가이드 — 제5회 BDAI 채용연계 공모전

## 준비

Python 3.10+ 에서:

```bash
pip install duckdb pyarrow pandas matplotlib
```

원본 데이터 `rtu_data_full.csv`(4.9GB)가 있는 폴더를 기준 경로로 사용합니다.
duckdb가 스트리밍 처리하므로 RAM 4GB 이하 노트북에서도 돌아갑니다.

## 실행 순서

```bash
# 0. (선택) 품질 확인 + 이상 신호 검증 — 콘솔 출력만, 수 분 소요
python 00_quality_check.py <데이터폴더>

# 1. 전처리: 5초 원본 → 1분/1시간 집계 parquet 생성 (필수, 1~2분)
python 01_preprocess.py <데이터폴더>
#    → <데이터폴더>/processed/agg_1min.parquet, agg_1h.parquet

# 2. EDA 차트 6종 생성 (1분 내외)
python 02_eda.py <데이터폴더>
#    → <데이터폴더>/eda_output/01~06_*.png
```

경로 인자를 생략하면 현재 폴더 기준.

## 한글 폰트

차트 한글이 □로 나오면 `02_eda.py` 상단의 폰트를 본인 환경에 맞게 수정:
- Windows: `plt.rcParams["font.family"] = "Malgun Gothic"`
- macOS: `"AppleGothic"`
- Linux: `"Noto Sans CJK JP"` 또는 `"NanumGothic"` (없으면 `sudo apt install fonts-nanum`)

## 데이터 컬럼 설명

### 원본 (rtu_data_full.csv)

3상 전력(R·S·T상) 계측이라 전압·전류·역률이 상별로 3개씩 존재.

| 컬럼 | 의미 | 이 데이터에서의 값 |
|---|---|---|
| `module(equipment)` | 계측기 번호(설비명). 예: `13(3호기)` | 13개 설비 |
| `timestamp` | 측정 시각 (Unix 밀리초) | 5초 간격 |
| `localtime` | 측정 시각 (YYYYMMDDHHMMSS) | timestamp와 동일 |
| `operation` | 설비 가동 여부 (1=가동) | 전 구간 1 → 정보량 없음 |
| `voltageR/S/T` | 상전압 (V) | 210~220V, 3호기만 190까지 하락 |
| `voltageRS/ST/TR` | 선간전압 (V, 상전압×√3) | ~365~377V |
| `currentR/S/T` | 상전류 (A) | 5~30A |
| `activePower` | 유효전력 (W) — 실제 일하는 전력, 요금의 기본 | 평균 ~3,010W |
| `powerFactorR/S/T` | 역률 (%) — 공급 전력 중 실제 일에 쓰인 비율 | 85~100, 예비건조기·6호기는 60·70까지 붕괴 |
| `reactivePowerLagging` | 지상 무효전력 (Var) — 모터 코일 등이 소비하는 "일 안 하는" 전력 | ~90~1,550 |
| `accumActiveEnergy` | 누적 전력량 (Wh) — 계량기처럼 계속 증가, 차분하면 기간 사용량 | 설비당 ~10.8MWh/5개월 |

비유: 유효전력=맥주, 무효전력=거품, 역률=잔에서 맥주 비율. 거품이 많으면 같은 일에 더 굵은 전선·큰 변압기가 필요하고, 한전은 역률 90% 미만 시 페널티 요금 부과 → 역률 붕괴를 비효율로 정의한 근거.

### 집계 (processed/agg_1min.parquet, agg_1h.parquet, agg_1h.csv)

| 컬럼 | 의미 |
|---|---|
| `module`, `ts` | 설비명, 집계 구간 시작 시각 |
| `activePower_mean/max/min` | 구간 내 유효전력 평균/최대/최소 (W) |
| `powerFactor_mean` | 3상 평균 역률의 구간 평균 (%) |
| `reactivePower_mean` | 무효전력 평균 (Var) |
| `currentSum_mean` | 3상 전류 합의 평균 (A, 1분 집계만) |
| `operation_ratio` | 구간 내 가동 비율 (0~1) |
| `accumEnergy_last` | 구간 마지막 누적 전력량 (Wh) |
| `n_samples` | 집계에 쓰인 원본 행 수 (1분=12, 1시간=720이면 결측 없음) |

## 파일 설명

| 파일 | 역할 |
|---|---|
| `00_quality_check.py` | 결측·값범위·이상신호 존재 검증 (EDA 결론의 근거 쿼리) |
| `01_preprocess.py` | 33.7M행 원본을 설비×1분/1시간 집계로 축약 |
| `02_eda.py` | 운영 특성 + 이상 신호 차트 6종 생성 |
| `../eda_output/EDA_발견사항_정리.md` | 발견 사항·리포트 방향 정리 (먼저 읽을 것) |

## 핵심 결론 요약

1. 13개 설비 모두 24시간 균일 부하 — 시간대/요일/월 패턴 없음 → 부하량 기반 분석 불가
2. 비효율 신호는 설비 3개의 전력 품질 이상뿐:
   - 3호기: 전압 강하(190~208V, 0.5%)
   - 예비건조기: 역률 붕괴(60~75%, 1.0%)
   - 6호기: 역률 붕괴(70~85%, 1.0%)
3. 셋 다 5초 단발성(run≈1), 전 기간 만성 발생 → 윈도우 빈도 집계 기반 탐지 모델 설계 필요
