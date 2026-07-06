# -*- coding: utf-8 -*-
"""
02_eda.py — 운영 특성 분석 + 비효율(이상) 신호 시각화
입력:  rtu_data_full.csv, processed/agg_1h.parquet
출력:  eda_output/*.png, eda_output/extracts/*.parquet (차트용 소규모 추출물)
사용법: python 02_eda.py [데이터 폴더 경로]
"""
import sys
from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

plt.rcParams["font.family"] = "Noto Sans CJK JP"   # 한글 폰트
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
SRC = BASE / "rtu_data_full.csv"
H1 = BASE / "processed" / "agg_1h.parquet"
OUT = BASE / "eda_output"
EXT = OUT / "extracts"
EXT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
con.execute("SET memory_limit='1.5GB'; SET threads=4;")

MOD_ORDER = ['1(PM-3)','2(L-1전등)','3(분쇄기(2))','4(분쇄기(1))','5(좌측분전반)',
             '11(우측분전반1)','12(4호기)','13(3호기)','14(2호기)','15(예비건조기)',
             '16(호이스트)','17(6호기)','18(우측분전반2)']

# ---------- 원본 1회 스캔으로 차트용 추출물 생성 ----------
if not (EXT / "minpf_sample.parquet").exists():
    # (a) 설비별 최소상 역률 샘플 (0.5%)
    con.execute(f"""
    COPY (SELECT "module(equipment)" AS module,
                 least(powerFactorR,powerFactorS,powerFactorT) AS minPF
          FROM read_csv('{SRC}', header=true) USING SAMPLE 0.5% (system))
    TO '{EXT / "minpf_sample.parquet"}' (FORMAT parquet)""")
    # (b) 설비별 최소상 전압 샘플 (0.5%)
    con.execute(f"""
    COPY (SELECT "module(equipment)" AS module,
                 least(voltageR,voltageS,voltageT) AS minV
          FROM read_csv('{SRC}', header=true) USING SAMPLE 0.5% (system))
    TO '{EXT / "minv_sample.parquet"}' (FORMAT parquet)""")
    # (c) 이상 이벤트 전체 (일자별 카운트용)
    con.execute(f"""
    COPY (SELECT "module(equipment)" AS module,
                 strptime(CAST(localtime AS VARCHAR),'%Y%m%d%H%M%S') AS ts,
                 least(voltageR,voltageS,voltageT) AS minV,
                 least(powerFactorR,powerFactorS,powerFactorT) AS minPF
          FROM read_csv('{SRC}', header=true)
          WHERE ("module(equipment)"='13(3호기)' AND least(voltageR,voltageS,voltageT)<210)
             OR ("module(equipment)" IN ('15(예비건조기)','17(6호기)')
                 AND least(powerFactorR,powerFactorS,powerFactorT)<85))
    TO '{EXT / "anomaly_events.parquet"}' (FORMAT parquet)""")
    # (d) 예시 구간: 3호기 하루치 5초 원본 (2025-01-15)
    con.execute(f"""
    COPY (SELECT strptime(CAST(localtime AS VARCHAR),'%Y%m%d%H%M%S') AS ts,
                 activePower, least(voltageR,voltageS,voltageT) AS minV
          FROM read_csv('{SRC}', header=true)
          WHERE "module(equipment)"='13(3호기)'
            AND localtime BETWEEN 20250115000000 AND 20250115235959)
    TO '{EXT / "unit3_20250115.parquet"}' (FORMAT parquet)""")
print("extracts done")

# ---------- 차트 1: 설비별 총 전력량 ----------
e = con.execute(f"""
SELECT module, (max(accumEnergy_last)-min(accumEnergy_last))/1000.0 AS kWh
FROM read_parquet('{H1}') GROUP BY 1""").df().set_index("module").reindex(MOD_ORDER)
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.bar(range(len(e)), e["kWh"], color="#4C72B0")
ax.set_xticks(range(len(e))); ax.set_xticklabels(e.index, rotation=45, ha="right")
ax.set_ylabel("총 전력량 (kWh)")
ax.set_title("설비별 총 전력량 (2024-12 ~ 2025-04) — 설비 간 차이가 거의 없음")
fig.tight_layout(); fig.savefig(OUT / "01_설비별_총전력량.png", dpi=150); plt.close(fig)

# ---------- 차트 2: 시간대×요일 히트맵 (전 설비 합) ----------
hm = con.execute(f"""
SELECT dayofweek(ts) AS dow, hour(ts) AS hh, avg(activePower_mean) AS w
FROM read_parquet('{H1}') GROUP BY 1,2""").df()
piv = hm.pivot(index="dow", columns="hh", values="w") * 13 / 1000  # 설비 평균→전체 kW
fig, ax = plt.subplots(figsize=(11, 3.5))
im = ax.imshow(piv, aspect="auto", cmap="YlOrRd")
ax.set_yticks(range(7)); ax.set_yticklabels(["일","월","화","수","목","금","토"])
ax.set_xticks(range(0, 24, 2)); ax.set_xlabel("시각"); ax.set_ylabel("요일")
ax.set_title("요일×시간대 평균 부하 히트맵 — 주기 패턴 부재 (상시 균일 가동)")
fig.colorbar(im, label="kW"); fig.tight_layout()
fig.savefig(OUT / "02_요일x시간대_히트맵.png", dpi=150); plt.close(fig)

# ---------- 차트 3: 최소상 역률 분포 (설비별) ----------
pf = pd.read_parquet(EXT / "minpf_sample.parquet")
fig, ax = plt.subplots(figsize=(10, 5))
data = [pf.loc[pf["module"] == m, "minPF"] for m in MOD_ORDER]
bp = ax.boxplot(data, labels=MOD_ORDER, showfliers=True,
                flierprops=dict(marker=".", markersize=3, alpha=.4, markerfacecolor="#C44E52"))
ax.axhline(85, color="#C44E52", ls="--", lw=1, label="정상 하한(85)")
ax.set_xticklabels(MOD_ORDER, rotation=45, ha="right")
ax.set_ylabel("3상 중 최소 역률 (%)")
ax.set_title("설비별 최소상 역률 분포 — 예비건조기·6호기에서 역률 붕괴 이벤트")
ax.legend(); fig.tight_layout()
fig.savefig(OUT / "03_역률분포_설비별.png", dpi=150); plt.close(fig)

# ---------- 차트 4: 최소상 전압 분포 (설비별) ----------
v = pd.read_parquet(EXT / "minv_sample.parquet")
fig, ax = plt.subplots(figsize=(10, 5))
data = [v.loc[v["module"] == m, "minV"] for m in MOD_ORDER]
ax.boxplot(data, labels=MOD_ORDER, showfliers=True,
           flierprops=dict(marker=".", markersize=3, alpha=.4, markerfacecolor="#C44E52"))
ax.axhline(210, color="#C44E52", ls="--", lw=1, label="정상 하한(210V)")
ax.set_xticklabels(MOD_ORDER, rotation=45, ha="right")
ax.set_ylabel("3상 중 최소 전압 (V)")
ax.set_title("설비별 최소상 전압 분포 — 3호기에서만 전압 강하(sag) 이벤트")
ax.legend(); fig.tight_layout()
fig.savefig(OUT / "04_전압분포_설비별.png", dpi=150); plt.close(fig)

# ---------- 차트 5: 이상 이벤트 일별 발생 추이 ----------
ev = pd.read_parquet(EXT / "anomaly_events.parquet")
ev["day"] = ev["ts"].dt.date
ev["type"] = np.where(ev["module"] == "13(3호기)", "3호기 전압강하",
              np.where(ev["module"] == "15(예비건조기)", "예비건조기 저역률", "6호기 저역률"))
daily = ev.groupby(["day", "type"]).size().unstack(fill_value=0)
fig, ax = plt.subplots(figsize=(11, 4))
for c in daily.columns:
    ax.plot(daily.index, daily[c], lw=.9, label=c)
ax.set_ylabel("일별 이벤트 수"); ax.set_title("이상 이벤트 일별 발생 추이 — 전 기간 만성적 발생")
ax.legend(); fig.tight_layout()
fig.savefig(OUT / "05_이상이벤트_일별추이.png", dpi=150); plt.close(fig)

# ---------- 차트 6: 예시 구간 (3호기 2025-01-15, 5초 원본) ----------
u3 = pd.read_parquet(EXT / "unit3_20250115.parquet").sort_values("ts")
fig, axes = plt.subplots(2, 1, figsize=(11, 5), sharex=True)
axes[0].plot(u3["ts"], u3["activePower"], lw=.3, color="#4C72B0")
axes[0].set_ylabel("유효전력 (W)")
axes[0].set_title("3호기 2025-01-15 (5초 원본) — 전력은 정상 범위, 전압만 간헐 강하")
sag = u3[u3["minV"] < 210]
axes[1].plot(u3["ts"], u3["minV"], lw=.3, color="#55A868")
axes[1].scatter(sag["ts"], sag["minV"], color="#C44E52", s=12, zorder=3, label="전압강하 이벤트")
axes[1].axhline(210, color="#C44E52", ls="--", lw=1)
axes[1].set_ylabel("최소상 전압 (V)"); axes[1].legend()
fig.tight_layout(); fig.savefig(OUT / "06_3호기_예시구간.png", dpi=150); plt.close(fig)

print("charts done:", sorted(p.name for p in OUT.glob("*.png")))
