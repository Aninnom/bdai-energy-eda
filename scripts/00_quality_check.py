# -*- coding: utf-8 -*-
"""
00_quality_check.py — 데이터 품질 확인 + 이상 신호 존재 검증 (콘솔 출력)
EDA 결론의 근거가 된 검증 쿼리 모음. 원본 CSV만 있으면 실행 가능 (전처리 불필요).
사용법: python 00_quality_check.py [데이터 폴더 경로]
소요: 풀스캔 쿼리 여러 개라 수 분 걸릴 수 있음
"""
import sys
from pathlib import Path
import duckdb

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
SRC = BASE / "rtu_data_full.csv"

con = duckdb.connect()
con.execute("SET memory_limit='1.5GB'; SET threads=4;")

def show(title, sql):
    print(f"\n=== {title} ===")
    print(con.execute(sql).df().to_string(index=False))

# 1) 설비별 수집 기간·결측 확인 → 13개 설비 모두 5초 간격 100% 커버리지
show("설비별 수집 기간 / 샘플 수", f"""
SELECT "module(equipment)" AS module,
       min(strptime(CAST(localtime AS VARCHAR),'%Y%m%d%H%M%S')) AS start,
       max(strptime(CAST(localtime AS VARCHAR),'%Y%m%d%H%M%S')) AS "end",
       count(*) AS n_rows,
       sum(CASE WHEN activePower IS NULL THEN 1 ELSE 0 END) AS null_power
FROM read_csv('{SRC}', header=true) GROUP BY 1 ORDER BY 1""")

# 2) 값 범위 점검 → 정상범위(V 210~220, PF 85~100)를 벗어나는 설비 발견
show("설비별 값 범위 (min/max)", f"""
SELECT "module(equipment)" AS module,
  min(least(voltageR,voltageS,voltageT))       AS v_min,
  max(greatest(voltageR,voltageS,voltageT))    AS v_max,
  min(least(powerFactorR,powerFactorS,powerFactorT)) AS pf_min,
  min(activePower) AS p_min, max(activePower)  AS p_max,
  round(avg(operation),3)                      AS op_mean
FROM read_csv('{SRC}', header=true) GROUP BY 1 ORDER BY 1""")

# 3) 이상 신호 규모 → 3호기 전압강하, 예비건조기·6호기 저역률만 존재
show("이상 신호 발생 규모", f"""
SELECT "module(equipment)" AS module,
  sum(CASE WHEN least(powerFactorR,powerFactorS,powerFactorT)<85 THEN 1 ELSE 0 END) AS rows_pf_lt85,
  sum(CASE WHEN least(voltageR,voltageS,voltageT)<210 THEN 1 ELSE 0 END) AS rows_v_lt210,
  count(*) AS total
FROM read_csv('{SRC}', header=true)
GROUP BY 1 HAVING rows_pf_lt85>0 OR rows_v_lt210>0 ORDER BY 1""")

# 4) 이상이 연속 구간인지 단발성인지 → run 평균 1.0 (5초 점 이상)
show("이상 run 길이 (연속성)", f"""
WITH a AS (
  SELECT "module(equipment)" AS module, timestamp/1000 AS t
  FROM read_csv('{SRC}', header=true)
  WHERE ("module(equipment)"='13(3호기)' AND least(voltageR,voltageS,voltageT)<210)
     OR ("module(equipment)" IN ('15(예비건조기)','17(6호기)')
         AND least(powerFactorR,powerFactorS,powerFactorT)<85)
), r AS (
  SELECT module, t,
    CASE WHEN t - lag(t) OVER (PARTITION BY module ORDER BY t) = 5 THEN 0 ELSE 1 END AS new_run
  FROM a
), g AS (
  SELECT module, sum(new_run) OVER (PARTITION BY module ORDER BY t) AS run_id FROM r
)
SELECT module, count(*) AS n_runs, round(avg(run_len),2) AS avg_len, max(run_len) AS max_len
FROM (SELECT module, run_id, count(*) AS run_len FROM g GROUP BY 1,2) GROUP BY 1""")

# 5) 시간 패턴 부재 확인 → 시간대별 평균이 사실상 동일
show("시간대별 평균 유효전력 (설비 평균, W)", f"""
SELECT hour(strptime(CAST(localtime AS VARCHAR),'%Y%m%d%H%M%S')) AS hh,
       round(avg(activePower),1) AS avg_W
FROM read_csv('{SRC}', header=true) GROUP BY 1 ORDER BY 1""")

print("\n완료. 해석은 eda_output/EDA_발견사항_정리.md 참고")
