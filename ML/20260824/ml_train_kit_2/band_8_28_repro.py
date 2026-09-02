# -*- coding: utf-8 -*-
"""8/28 에 준 밴드 적중률이 오염 표본이었나 — 재현 (2026-09-01)

매입 파트 문의(#67)에 답하기 위한 것입니다.

    8/28 에 준 값   경락 배추 80.0 · 무 80.4 · 양파 69.7
    각주            "양파 69.7% 는 명목 미달 — 구간이 실제 불확실성을 과소 표현"

이번 정정에서 양파가 제일 나은 품목으로 뒤집혔으므로, 적중률도 같은
오염 표본이었는지 확인이 필요합니다.

## 방법

8/28 시점의 `prediction_log` 를 되살려 두 가지로 잽니다.

    (가) 그때 그대로       ops_* 와 ops-*/old-*/ung-*/bnd-* 가 섞인 상태
    (나) 운영 기록만       model_ver 이 ops_auc · ops_whsl · ops_rtl 인 행만

    지금 표(실험 행 걷어낸 것)  +  실험백업 CSV  =  8/28 당시 상태

**적중은 pred_lo ~ pred_hi 안에 actual_prc 가 들어왔나** 입니다.
적재 시점에 이미 계산돼 저장된 값이라 다시 만들지 않습니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import psycopg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_predictions import dsn                             # noqa: E402

BAK = HERE.parents[2] / "실험결과" / "prediction_log_실험백업_20260901.csv"
ITEMS = ["배추", "무", "양파"]
OLD = {"배추": 80.0, "무": 80.4, "양파": 69.7}
COLS = ["base_dt", "target_dt", "item_nm", "lead_biz_d", "target_kind",
        "pred_prc", "pred_lo", "pred_hi", "actual_prc", "model_ver"]


def load():
    with psycopg.connect(dsn(), connect_timeout=25) as c:
        cur = pd.read_sql(f"SELECT {','.join(COLS)} FROM prediction_log", c)
    bak = pd.read_csv(BAK, encoding="utf-8-sig")[COLS]
    for d in (cur, bak):
        for k in ("base_dt", "target_dt"):
            d[k] = pd.to_datetime(d[k])
    #   8/28 당시 상태 = 지금 남은 것 + 그날 이후 걷어낸 실험 행
    return pd.concat([cur, bak], ignore_index=True)


def measure(d, tag):
    d = d[d.actual_prc.notna() & d.pred_lo.notna() & d.pred_hi.notna()]
    d = d[d.target_kind == "auc"]
    if d.empty:
        print(f"  {tag}: 잴 행이 없습니다")
        return
    hit = (d.actual_prc >= d.pred_lo) & (d.actual_prc <= d.pred_hi)
    d = d.assign(hit=hit)
    print(f"\n  [{tag}]  {len(d):,}행 · 모델 {d.model_ver.nunique()}종 · "
          f"기준일 {d.base_dt.dt.date.nunique()}개")
    print(f"    {'품목':<6}{'행수':>9}{'적중률':>9}   (8/28 에 준 값)")
    for it in ITEMS:
        x = d[d.item_nm == it]
        if x.empty:
            continue
        print(f"    {it:<6}{len(x):>9,}{x.hit.mean()*100:>8.1f}%   {OLD[it]:>6.1f}%")
    print(f"    {'전체':<6}{len(d):>9,}{d.hit.mean()*100:>8.1f}%")


def main():
    d = load()
    print("=" * 68)
    print("[8/28 밴드 적중률 재현] 경락가 · prediction_log")
    print("=" * 68)
    print("  섞여 있던 모델 이름:")
    for v, n in d[d.target_kind == "auc"].model_ver.value_counts().items():
        print(f"    {v:<14}{n:>8,}행")

    measure(d, "가. 그때 그대로 — 실험 백테스트 섞임")
    measure(d[d.model_ver.isin(["ops_auc", "ops_whsl", "ops_rtl"])],
            "나. 운영 기록(ops_* 밑줄)만")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
