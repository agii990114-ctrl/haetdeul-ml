# -*- coding: utf-8 -*-
"""앵커 α 재판정 — 5개 값 × 3타겟 × 2폴드 (2026-08-28 · 2차).

1차와 다른 점 두 가지. 둘 다 1차 결과를 무효로 만든다.
  ① 원본 앵커 컬럼을 덮어쓰던 버그를 고쳤다.
     baseline ①"어제 가격" 이 수축 앵커로 바뀌어 있었다.
  ② 수축 앵커(α 0.2~0.8)를 baseline 후보에 넣었다.
     수축 앵커는 모델 없이 계산되는 값이다. 후보에서 빼면
     "단순 규칙을 개선해 놓고 모델 공로로 돌리는" 것이 된다.
"""
import itertools
import subprocess
import sys
import time
from pathlib import Path

CSV = "train_20260828b.csv"
SEEDS = ["42", "43", "44", "45", "46"]
FOLDS = [("A", "2022-12-31", "2023-12-31"), ("B", "2021-12-31", "2022-12-31")]
TARGETS = ["auc", "whsl", "rtl"]
ALPHAS = ["1.0", "0.8", "0.6", "0.4", "0.2"]

out = Path("results/alpha5_20260828")
out.mkdir(parents=True, exist_ok=True)
n = 0
for tgt, (fold, tr_end, va_end), al in itertools.product(TARGETS, FOLDS, ALPHAS):
    tag = f"{tgt}_fold{fold}_a{al.replace('.', '')}"
    cmd = [sys.executable, "train.py", CSV, "--target", tgt,
           "--train-start", "2017-01-01", "--train-end", tr_end,
           "--valid-end", va_end, "--gate-lt", "3",
           "--anchor-alpha", al, "--seeds", *SEEDS]
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    (out / f"{tag}.txt").write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
    n += 1
    print(f"[{n:>2}/30] {tag:<22} rc={r.returncode} ({time.time()-t:.0f}초)", flush=True)
print("완료")
