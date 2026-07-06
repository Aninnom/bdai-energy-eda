# 제5회 BDAI 채용연계 데이터 분석 공모전

제조공장 전력·설비 운영 데이터(RTU) 기반 에너지 비효율 구간 탐지 — 팀 분석 리포지토리

## 구조

```
scripts/        분석 코드 (실행 방법은 scripts/README.md)
eda_output/     EDA 차트 + 발견사항 정리 (EDA_발견사항_정리.md 먼저 읽기)
processed/      전처리 산출물 (git 미포함, 01_preprocess.py로 생성)
rtu_data_full.csv  원본 데이터 (git 미포함, LMS 공모전 탭에서 다운로드)
```

## 빠른 시작

```bash
pip install duckdb pyarrow pandas matplotlib
python scripts/01_preprocess.py .   # 5초 원본 → 1분/1시간 집계
python scripts/02_eda.py .          # 차트 6종 생성
```

## 핵심 발견 (2026-07-07 EDA 기준)

1. 13개 설비 모두 24시간 균일 부하 — 시간대·요일·월 패턴 없음
2. 비효율 신호는 설비 3개의 전력 품질 이상: 3호기 전압강하(0.5%), 예비건조기 역률붕괴(1.0%), 6호기 역률붕괴(1.0%)
3. 모두 5초 단발성 점 이상, 전 기간 만성 발생 → 윈도우 빈도 기반 탐지 모델 설계 방향

상세: [eda_output/EDA_발견사항_정리.md](eda_output/EDA_발견사항_정리.md)

## 일정

- 1차 서류(분석 리포트 PDF) 마감: **2026-07-12(일)**
- 2차 발표자료 제출: 2026-07-26 / 본선 발표: 2026-08-01
