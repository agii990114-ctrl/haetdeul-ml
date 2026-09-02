# -*- coding: utf-8 -*-
"""앵커 α 판정 — 3타겟 × 2폴드 × α 2가지 (2026-08-28).

exp_anchor.py 와 train.py 의 α=1.0 수치가 미세하게 달라(0.1757 vs 0.1754)
어느 쪽이 맞는지 알 수 없었다. train.py 한 코드로 통일해 다시 잰다.
발표·논문에 쓸 숫자는 여기서 나온 것만 쓴다.
"""
import subprocess, sys, itertools, time
from pathlib import Path

CSV = "train_20260828b.csv"
SEEDS = ["42", "43", "44", "45", "46"]
FOLDS = [("A", "2022-12-31", "2023-12-31"), ("B", "2021-12-31", "2022-12-31")]
TARGETS = ["auc", "whsl", "rtl"]
ALPHAS = ["1.0", "0.6"]

out = Path("results/alpha_20260828")
out.mkdir(parents=True, exist_ok=True)
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
    print(f"[{tag}] rc={r.returncode} ({time.time()-t:.0f}초)", flush=True)
print("완료")
