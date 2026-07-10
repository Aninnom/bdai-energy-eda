# -*- coding: utf-8 -*-
"""
07_ablation_experiment.py — 피처 소거 실험 (Ablation Study)
04_isolation_forest.py의 설계 결정(품질 3피처 + max_samples=2048)의 근거 실험.
대상: 15(예비건조기) — 역률 붕괴 이벤트 보유 설비.
평가: 규칙 준거 라벨(minPF<85) 대비 PR-AUC, Precision@k (k=실제 이상 수)

참고: 본문 리포트의 수치는 전체 2,592,001행 스코어링 기준이며,
      본 스크립트는 재현 편의를 위해 평가 표본 500,000행을 사용 (경향 동일).
사용법: python 07_ablation_experiment.py [데이터 폴더 경로]
"""
import sys, glob, urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score

SEED = 42
N_TRAIN = 100_000
N_EVAL = 500_000
TARGET = "15(예비건조기)"

QUALITY = ["minV", "vImbalance", "minPF"]          # 전력 품질 피처
LOAD = ["p", "q", "iSum"]                           # 부하 피처 (1단계에서 이상 없음 확인)

CONFIGS = [
    ("품질+부하 6피처", QUALITY + LOAD, 256),
    ("품질 3피처",      QUALITY,        256),
    ("품질 3피처",      QUALITY,        2048),   # <- 채택
    ("품질 3피처",      QUALITY,        8192),
    ("minPF 단독",      ["minPF"],      8192),
]

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
part = next(p for p in (BASE / "features").glob("module=*")
            if urllib.parse.unquote(p.name.split("=", 1)[1]) == TARGET)
df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(part / "*.parquet")))],
               ignore_index=True)
y_all = ((df["label_e1"] + df["label_e2"]) > 0).astype(int).values

rng = np.random.RandomState(SEED)
train_idx = rng.choice(len(df), N_TRAIN, replace=False)
eval_idx = rng.choice(len(df), N_EVAL, replace=False)
y = y_all[eval_idx]
k = int(y.sum())

print(f"대상: {TARGET}, 학습 {N_TRAIN:,} / 평가 {N_EVAL:,}행 (이상 {k:,}건)\n")
print(f"{'구성':<18}{'max_samples':>12}{'PR-AUC':>10}{'P@k':>8}")
for name, feats, ms in CONFIGS:
    model = IsolationForest(n_estimators=150, max_samples=ms,
                            random_state=SEED, n_jobs=4).fit(df.loc[train_idx, feats].values)
    s = -model.score_samples(df.loc[eval_idx, feats].values)
    thr = np.partition(s, -k)[-k]
    p_at_k = ((s >= thr) & (y == 1)).sum() / (s >= thr).sum()
    mark = "  <- 채택" if (feats == QUALITY and ms == 2048) else ""
    print(f"{name:<18}{ms:>12}{average_precision_score(y, s):>10.3f}{p_at_k:>8.3f}{mark}")

print("\n결론: 부하 피처 포함 시 노이즈 극단값이 점수를 잠식해 성능 급락.")
print("품질 3피처 + max_samples=2048 채택 (04_isolation_forest.py).")
