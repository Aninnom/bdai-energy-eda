# -*- coding: utf-8 -*-
"""
06_savings_estimate.py — 절감 잠재량 환산 (kWh → 전기요금 → 탄소배출량)
모든 이벤트 통계는 features/ 데이터에서 직접 산출 (하드코딩 없음).
수식·가정·출처: docs/05_절감잠재량_환산.md

사용법: python 06_savings_estimate.py [데이터 폴더 경로]
"""
import sys, glob, math, urllib.parse
from pathlib import Path
import pandas as pd

# ===== 환산 계수 및 가정 (docs/05 참조) =====
TARIFF_KRW_PER_KWH = 179.0    # 산업용 평균 판매단가 (2025 상반기, 한전)
CO2_KG_PER_KWH = 0.4173       # 국가 전력배출계수 (2023년 공표, 최신)
ALPHA_LINE_LOSS = 0.03        # 공장 내부 배전(선로) 손실률 가정: 부하의 3%
CONTRACT_KW = 50              # 계약전력 가정 (13개 설비 평균부하 39.1kW 기준 상향)
BASE_KRW_PER_KW = 9000        # 기본요금 단가 가정 (원/kW·월, 산업용 고압A 수준)
PF_PENALTY_PER_PCT = 0.002    # 한전 기본공급약관 제43조: 지상역률 90% 미달 1%p당 0.2%
SAMPLE_SEC = 5
PERIOD_DAYS = 150             # 2024-12-01 ~ 2025-04-29 (완전한 날짜 기준)
ANNUALIZE = 365 / PERIOD_DAYS

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

def load(module, cols):
    part = next(p for p in (BASE / "features").glob("module=*")
                if urllib.parse.unquote(p.name.split("=", 1)[1]) == module)
    return pd.concat([pd.read_parquet(f, columns=cols)
                      for f in sorted(glob.glob(str(part / "*.parquet")))], ignore_index=True)

print("=" * 70)
print("① 실측 이벤트 기준: 저역률 이벤트의 선로 손실 증분 (I²R 모델)")
print("=" * 70)
total_kwh_yr = 0.0
sustained_w = 0.0
for m in ["15(예비건조기)", "17(6호기)"]:
    df = load(m, ["minPF", "p", "label_e2"])
    ev = df[df.label_e2 == 1]
    pf_normal = df.loc[df.label_e2 == 0, "minPF"].median()
    pf_event = ev["minPF"].median()
    p_mean = df["p"].mean()                     # W
    hours_event = len(ev) * SAMPLE_SEC / 3600   # 이벤트 총 시간
    # 영향 상(1/3 부하)의 기준 선로손실 × 손실 배율 증가분
    base_loss_w = ALPHA_LINE_LOSS * p_mean / 3
    delta_w = base_loss_w * ((pf_normal / pf_event) ** 2 - 1)
    kwh_5mo = delta_w * hours_event / 1000
    kwh_yr = kwh_5mo * ANNUALIZE
    total_kwh_yr += kwh_yr
    sustained_w += delta_w
    print(f"{m}: 이벤트 {len(ev):,}건({hours_event:.1f}h), "
          f"역률 {pf_normal:.1f}%→{pf_event:.1f}%, 손실증분 {delta_w:.1f}W")
    print(f"   → {kwh_5mo:.2f} kWh/5개월 = {kwh_yr:.1f} kWh/년")
print(f"\n합계(연간): {total_kwh_yr:.1f} kWh "
      f"= {total_kwh_yr * TARIFF_KRW_PER_KWH:,.0f}원 "
      f"= {total_kwh_yr * CO2_KG_PER_KWH:.1f} kgCO₂")
print("→ 이벤트가 전체 시간의 약 1%(5초 단발)라 현재 손실은 미미.")
print("  본 모델의 경제적 가치는 ②·③의 예방에 있음.")

print()
print("=" * 70)
print("② 열화 상시화 방지 시나리오 (조기 정비의 예방 가치, 연간)")
print("=" * 70)
sus_kwh = sustained_w * 8760 / 1000
print(f"(a) 저역률이 상시화될 경우 초과 선로손실: {sustained_w:.1f}W × 8,760h "
      f"= {sus_kwh:.0f} kWh = {sus_kwh * TARIFF_KRW_PER_KWH:,.0f}원 "
      f"= {sus_kwh * CO2_KG_PER_KWH:.0f} kgCO₂")

# 청구 역률(P,Q 기반) 현황과 페널티 시나리오
df15 = load("15(예비건조기)", ["p", "q"])
pf_bill = df15["p"].mean() / math.hypot(df15["p"].mean(), df15["q"].mean()) * 100
pf_deg = 63.0  # 열화 상시화 시 청구 역률 가정 (이벤트 중앙값 수준)
penalty_mo = CONTRACT_KW * BASE_KRW_PER_KW * (90 - pf_deg) * PF_PENALTY_PER_PCT
print(f"(b) 현재 청구 기준 역률(P,Q): {pf_bill:.1f}% → 페널티 없음")
print(f"    열화로 청구 역률이 {pf_deg:.0f}%까지 하락 시: "
      f"기본요금의 {(90 - pf_deg) * PF_PENALTY_PER_PCT * 100:.1f}% 가산 "
      f"= {penalty_mo:,.0f}원/월 = {penalty_mo * 12:,.0f}원/년")

print()
print("=" * 70)
print("③ 전압강하(3호기) — 다운타임 회피 가치 (파라미터식)")
print("=" * 70)
df13 = load("13(3호기)", ["label_e1"])
n_sag = int(df13.label_e1.sum())
print(f"관측된 전압강하 이벤트: {n_sag:,}건/5개월 (법정 유지범위 207V 미달 포함)")
print("회피 가치 = (방지된 정지 횟수/년) × (평균 정지 시간 h) × (시간당 생산손실 L원)")
print("→ L은 공정별 상이하므로 리포트에는 수식과 파라미터로 제시 (임의 숫자 지양)")
