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
