# -*- coding: utf-8 -*-
"""
03_features.py — 탐지 모델 입력 피처 추출
원본 5초 데이터에서 시점 단위 다변량 피처 + 규칙 준거 라벨(E1/E2)을 생성.
모델에는 피처만 입력되며, 라벨은 4단계 성능 평가에만 사용한다 (누설 없음).

출력: features/module=<설비>/*.parquet (설비별 파티션)
사용법: python 03_features.py [데이터 폴더 경로]
"""
import sys
from pathlib import Path
import duckdb

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
SRC = BASE / "rtu_data_full.csv"
OUT = BASE / "features"

con = duckdb.connect()
con.execute("SET memory_limit='1.5GB'; SET threads=4; SET preserve_insertion_order=false;")

con.execute(f"""
COPY (
    SELECT
        "module(equipment)"                                   AS module,
        timestamp,
        -- ===== 모델 입력 피처 (시점 단위 다변량) =====
        least(voltageR, voltageS, voltageT)                   AS minV,       -- 3상 최소 전압
        greatest(voltageR, voltageS, voltageT)
          - least(voltageR, voltageS, voltageT)               AS vImbalance, -- 상간 불균형
        least(powerFactorR, powerFactorS, powerFactorT)       AS minPF,      -- 3상 최소 역률
        activePower                                           AS p,
        reactivePowerLagging                                  AS q,
        currentR + currentS + currentT                        AS iSum,
        -- ===== 규칙 준거 라벨 (평가 전용, 모델 입력 아님) =====
        CASE WHEN least(voltageR, voltageS, voltageT) < 210   THEN 1 ELSE 0 END AS label_e1,
        CASE WHEN least(powerFactorR, powerFactorS, powerFactorT) < 85 THEN 1 ELSE 0 END AS label_e2
    FROM read_csv('{SRC}', header=true)
) TO '{OUT}' (FORMAT parquet, PARTITION_BY (module), OVERWRITE_OR_IGNORE)
""")
print("features done ->", OUT)
