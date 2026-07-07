# -*- coding: utf-8 -*-
"""
05_evaluation.py — 탐지 결과 분석·성능 평가 차트 (4단계)
1) PR 곡선 (이상 설비 3개)
2) 이상 점수 vs minPF / minV 산점도 — 모델이 임계값을 배우지 않고도 경계를 학습했는지
3) 정상 vs 이상 설비 점수 분포 비교
사용법: python 05_evaluation.py [데이터 폴더 경로] [차트번호 1|2|3, 생략 시 전부]
"""
import sys, glob, urllib.parse
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve, average_precision_score

plt.rcParams["font.family"] = "Noto Sans CJK JP"
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
ONLY = int(sys.argv[2]) if len(sys.argv) > 2 else None
MO = BASE / "model_output"
OUT = BASE / "eda_output"
ANOM = ["13(3호기)", "15(예비건조기)", "17(6호기)"]

def load_scores(module):
    return pd.read_parquet(MO / f"scores_{module}.parquet")

def load_features(module, cols):
    part = next(p for p in (BASE / "features").glob("module=*")
                if urllib.parse.unquote(p.name.split("=", 1)[1]) == module)
    fs = sorted(glob.glob(str(part / "*.parquet")))
    return pd.concat([pd.read_parquet(f, columns=cols + ["timestamp"]) for f in fs], ignore_index=True)

# ---------- 차트 7: PR 곡선 ----------
if ONLY in (None, 1):
    fig, ax = plt.subplots(figsize=(7, 5.5))
    for m in ANOM:
        d = load_scores(m)
        pr, rc, _ = precision_recall_curve(d["label"], d["score"])
        ap = average_precision_score(d["label"], d["score"])
        ax.plot(rc, pr, lw=1.6, label=f"{m} (PR-AUC {ap:.3f})")
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision")
    ax.set_title("Isolation Forest 탐지 성능 — 규칙 준거 라벨 대비 PR 곡선")
    ax.legend(loc="lower left"); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(OUT / "07_PR곡선.png", dpi=150); plt.close(fig)
    print("chart 7 done")

# ---------- 차트 8: 점수 vs 지표 산점도 (경계 학습 증명) ----------
if ONLY in (None, 2):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    rng = np.random.RandomState(0)
    # (좌) 예비건조기: score vs minPF
    m = "15(예비건조기)"
    d = load_scores(m).merge(load_features(m, ["minPF"]), on="timestamp")
    samp = pd.concat([d[d.label == 1], d[d.label == 0].sample(150_000, random_state=0)])
    axes[0].scatter(samp["minPF"], samp["score"], s=1.5, alpha=.25,
                    c=np.where(samp["label"] == 1, "#C44E52", "#4C72B0"))
    axes[0].axvline(85, color="#C44E52", ls="--", lw=1.2, label="준거 기준 85% (모델 미입력)")
    axes[0].set_xlabel("3상 중 최소 역률 (%)"); axes[0].set_ylabel("이상 점수")
    axes[0].set_title(f"{m}: 점수 vs 역률"); axes[0].legend(loc="upper right")
    # (우) 3호기: score vs minV
    m = "13(3호기)"
    d = load_scores(m).merge(load_features(m, ["minV"]), on="timestamp")
    samp = pd.concat([d[d.label == 1], d[d.label == 0].sample(150_000, random_state=0)])
    axes[1].scatter(samp["minV"], samp["score"], s=1.5, alpha=.25,
                    c=np.where(samp["label"] == 1, "#C44E52", "#4C72B0"))
    axes[1].axvline(210, color="#C44E52", ls="--", lw=1.2, label="준거 기준 210V (모델 미입력)")
    axes[1].set_xlabel("3상 중 최소 전압 (V)"); axes[1].set_ylabel("이상 점수")
    axes[1].set_title(f"{m}: 점수 vs 전압"); axes[1].legend(loc="upper right")
    fig.suptitle("모델은 임계값을 입력받지 않았지만 경계 아래에서 점수가 급등한다", y=1.02)
    fig.tight_layout(); fig.savefig(OUT / "08_경계학습_산점도.png", dpi=150, bbox_inches="tight"); plt.close(fig)
    print("chart 8 done")

# ---------- 차트 9: 정상 vs 이상 설비 점수 분포 ----------
if ONLY in (None, 3):
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bins = np.linspace(0.3, 0.85, 120)
    d_norm = load_scores("14(2호기)")
    ax.hist(d_norm["score"], bins=bins, density=True, alpha=.55, label="정상 설비 예: 2호기", color="#4C72B0")
    d_an = load_scores("15(예비건조기)")
    ax.hist(d_an.loc[d_an.label == 1, "score"], bins=bins, density=True, alpha=.55,
            label="예비건조기의 라벨 이상 샘플", color="#C44E52")
    ax.set_yscale("log"); ax.set_xlabel("이상 점수"); ax.set_ylabel("밀도 (log)")
    ax.set_title("정상 설비 점수 분포 vs 이상 샘플 점수 분포 — 뚜렷한 분리")
    ax.legend(); fig.tight_layout()
    fig.savefig(OUT / "09_점수분포_비교.png", dpi=150); plt.close(fig)
    print("chart 9 done")
