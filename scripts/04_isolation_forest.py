# -*- coding: utf-8 -*-
"""
04_isolation_forest.py — 설비별 Isolation Forest 학습·스코어링·평가
설계 (docs/02 + 모델 선택 논리):
  - 설비별 독립 모델 13개: 각 설비가 "자기 자신의 정상"을 학습
  - 입력 피처: 전력 품질 3종 (minV, vImbalance, minPF). 임계값·라벨 미입력.
    * 부하 피처(p, q, iSum) 제외 근거: 1단계에서 부하 지표는 전 설비 정상 확인.
      포함 시 노이즈 극단값이 점수를 잠식 → 피처 소거 실험(예비건조기):
      6피처 PR-AUC 0.093 vs 품질 3피처 0.925
  - max_samples=2048: 256(기본)→0.764, 2048→0.925, 8192→0.886 실험으로 선택
  - 학습: 설비당 무작위 100,000 샘플 / 스코어링: 전체 2,592,001행
  - 평가: 규칙 준거 라벨(E1∪E2) 대비 PR-AUC, P/R@k (k=실제 이상 수)

출력: model_output/scores_<설비>.parquet, model_output/summary.csv
사용법: python 04_isolation_forest.py [데이터 폴더 경로]
"""
import sys, time, urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score

SEED = 42
FEATURES = ["minV", "vImbalance", "minPF"]
N_TRAIN = 100_000

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
FEAT_DIR = BASE / "features"
OUT = BASE / "model_output"
OUT.mkdir(exist_ok=True)

PARTIAL = OUT / "summary_partial.csv"

rows = []
for part in sorted(FEAT_DIR.glob("module=*")):
    module = urllib.parse.unquote(part.name.split("=", 1)[1])
    if (OUT / f"scores_{module}.parquet").exists():   # 재실행 시 완료분 스킵
        continue
    t0 = time.time()
    df = pd.concat([pd.read_parquet(f) for f in part.glob("*.parquet")], ignore_index=True)
    y = ((df["label_e1"] + df["label_e2"]) > 0).astype(int).values  # 평가 전용

    # ----- 학습 (라벨 미사용) -----
    rng = np.random.RandomState(SEED)
    idx = rng.choice(len(df), size=min(N_TRAIN, len(df)), replace=False)
    model = IsolationForest(
        n_estimators=150, max_samples=2048, contamination="auto",
        random_state=SEED, n_jobs=4,
    ).fit(df.loc[idx, FEATURES].values)

    # ----- 전체 스코어링 (점수 클수록 이상) -----
    score = -model.score_samples(df[FEATURES].values)

    # ----- 평가: PR-AUC + P/R@k -----
    n_true = int(y.sum())
    if n_true > 0:
        pr_auc = average_precision_score(y, score)
        thr = np.partition(score, -n_true)[-n_true]      # 상위 k=n_true 컷
        pred = score >= thr
        tp = int((pred & (y == 1)).sum())
        precision = tp / pred.sum()
        recall = tp / n_true
    else:
        pr_auc, precision, recall, thr = np.nan, np.nan, np.nan, np.nan

    pd.DataFrame({
        "timestamp": df["timestamp"], "score": score.astype("float32"),
        "label": y.astype("int8"),
    }).to_parquet(OUT / f"scores_{module}.parquet", index=False)

    row = {
        "module": module, "n": len(df), "n_anomaly_label": n_true,
        "pr_auc": round(pr_auc, 4) if n_true else None,
        "precision_at_k": round(precision, 4) if n_true else None,
        "recall_at_k": round(recall, 4) if n_true else None,
        "score_p50": round(float(np.median(score)), 4),
        "score_p999": round(float(np.quantile(score, 0.999)), 4),
        "score_max": round(float(score.max()), 4),
        "sec": round(time.time() - t0, 1),
    }
    rows.append(row)
    pd.DataFrame([row]).to_csv(PARTIAL, mode="a", header=not PARTIAL.exists(), index=False)
    print(f"{module}: n_true={n_true} pr_auc={row['pr_auc']} "
          f"P@k={row['precision_at_k']} R@k={row['recall_at_k']} ({row['sec']}s)", flush=True)

# 전 설비 완료 시 최종 summary 생성
if PARTIAL.exists() and len(pd.read_csv(PARTIAL)) == len(list(FEAT_DIR.glob("module=*"))):
    summary = pd.read_csv(PARTIAL).sort_values("module")
    summary.to_csv(OUT / "summary.csv", index=False)
    print("\n", summary.to_string(index=False))
