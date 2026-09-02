# -*- coding: utf-8 -*-
"""3타겟 x 2폴드 재측정 (2026-08-28).

왜 다시 재나:
  1) 경락가 타겟이 08-27 에 바뀌었다 (규격 혼합 -> 규격 고정)
  2) 그 여파로 중도매/소매의 입력도 바뀌었다
     (auc_prc_lag1 · auc_whsl_ratio_lag1 이 그쪽 feature 다)
  3) train.py 의 baseline 후보가 타겟과 어긋나 있던 것을 고쳤다
     -> 이전 개선율은 전부 "앵커 하나에만 댄 값" 이었다

폴드 두 개를 다 돌린다 (CLAUDE.md 5.7). 한 해로 판정하지 않는다.
"""
import subprocess, sys, itertools, time, json, re
from pathlib import Path

CSV = "train_20260828b.csv"
SEEDS = ["42", "43", "44", "45", "46"]
FOLDS = [
    ("A", "2022-12-31", "2023-12-31"),   # 검증 2023
    ("B", "2021-12-31", "2022-12-31"),   # 검증 2022 (태풍 힌남노 든 해)
]
TARGETS = ["auc", "whsl", "rtl"]

out_dir = Path("results/remeasure_20260828b")
out_dir.mkdir(parents=True, exist_ok=True)

for tgt, (fold, tr_end, va_end) in itertools.product(TARGETS, FOLDS):
    tag = f"{tgt}_fold{fold}"
    log = out_dir / f"{tag}.txt"
    cmd = [sys.executable, "train.py", CSV, "--target", tgt,
           "--train-start", "2017-01-01", "--train-end", tr_end,
           "--valid-end", va_end, "--gate-lt", "3", "--seeds", *SEEDS]
    t = time.time()
    print(f"[{tag}] 시작 ...", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    log.write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
    print(f"[{tag}] 종료 rc={r.returncode} ({time.time()-t:.0f}초) -> {log}", flush=True)
print("전부 완료")
