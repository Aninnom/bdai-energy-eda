# -*- coding: utf-8 -*-
"""
01_preprocess.py — 원본 5초 간격 RTU 데이터를 분석용으로 집계
입력:  rtu_data_full.csv (33.7M rows, 2024-12-01 ~ 2025-04-30, 설비 13개)
출력:  processed/agg_1min.parquet  (설비×1분 집계)
       processed/agg_1h.parquet   (설비×1시간 집계)
사용법: python 01_preprocess.py [데이터 폴더 경로]
"""
import sys
import duckdb
from pathlib import Path

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
SRC = BASE / "rtu_data_full.csv"
OUT = BASE / "processed"
OUT.mkdir(exist_ok=True)

con = duckdb.connect()
con.execute("SET memory_limit='1.5GB'; SET threads=4;")
con.execute("SET preserve_insertion_order=false;")

# localtime(YYYYMMDDHHMMSS)을 timestamp로 파싱, 컬럼명 정리
base_query = f"""
SELECT
    "module(equipment)"                                        AS module,
    strptime(CAST(localtime AS VARCHAR), '%Y%m%d%H%M%S')      AS ts,
    operation,
    activePower,
    (powerFactorR + powerFactorS + powerFactorT) / 3.0         AS powerFactor,
    reactivePowerLagging,
    (currentR + currentS + currentT)                           AS currentSum,
    accumActiveEnergy
FROM read_csv('{SRC}', header=true)
"""

# 1분 집계
con.execute(f"""
COPY (
    SELECT
        module,
        date_trunc('minute', ts)            AS ts,
        avg(activePower)                    AS activePower_mean,
        max(activePower)                    AS activePower_max,
        min(activePower)                    AS activePower_min,
        avg(powerFactor)                    AS powerFactor_mean,
        avg(reactivePowerLagging)           AS reactivePower_mean,
        avg(currentSum)                     AS currentSum_mean,
        avg(operation)                      AS operation_ratio,
        max(accumActiveEnergy)              AS accumEnergy_last,
        count(*)                            AS n_samples
    FROM ({base_query})
    GROUP BY 1, 2
    ORDER BY 1, 2
) TO '{OUT / "agg_1min.parquet"}' (FORMAT parquet)
""")
print("agg_1min.parquet done")

# 1시간 집계 (1분 집계에서 파생)
con.execute(f"""
COPY (
    SELECT
        module,
        date_trunc('hour', ts)              AS ts,
        avg(activePower_mean)               AS activePower_mean,
        max(activePower_max)                AS activePower_max,
        avg(powerFactor_mean)               AS powerFactor_mean,
        avg(reactivePower_mean)             AS reactivePower_mean,
        avg(operation_ratio)                AS operation_ratio,
        max(accumEnergy_last)               AS accumEnergy_last,
        sum(n_samples)                      AS n_samples
    FROM read_parquet('{OUT / "agg_1min.parquet"}')
    GROUP BY 1, 2
    ORDER BY 1, 2
) TO '{OUT / "agg_1h.parquet"}' (FORMAT parquet)
""")
print("agg_1h.parquet done")
