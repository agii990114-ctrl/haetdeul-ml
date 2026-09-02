# -*- coding: utf-8 -*-
"""LLM 여러 회차를 모아 판정한다 (2026-09-02)

## 왜 여러 번 재나

한 번 잘 나온 것으로는 정할 수 없다. **어제 MLP 를 기각한 이유가 정확히
"돌릴 때마다 답이 크게 달라진다" 였다.** 같은 잣대를 LLM 에도 댄다.

우리 규칙: **개선율이 편차의 2배를 넘어야** 의미가 있다 (CLAUDE.md §8).
LightGBM 은 시드 5개로 그 편차를 잰다. LLM 은 회차로 잰다.

## 쓰는 법

    python llm_summary.py            # 실험결과/llm_*_scored.csv 를 다 모은다
"""
from __future__ import annotations

import glob
import re
import statistics as st
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "실험결과"
ITEMS = ["배추", "무", "양파"]


def wm(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return np.abs(a - p).sum() / np.abs(a).sum()


def main() -> int:
    files = sorted(glob.glob(str(RES / "llm_*_scored.csv")))
    runs = {}
    for f in files:
        n = Path(f).stem
        #   llm_prompt_scored = 1차 · llm_runN_scored = N차
        m = re.search(r"run(\d+)", n)
        tag = f"{m.group(1)}차" if m else "1차"
        runs[tag] = pd.read_csv(f, encoding="utf-8-sig")
    if not runs:
        sys.exit("채점 파일이 없습니다.")
    tags = sorted(runs, key=lambda t: int(t[0]))

    #   회차마다 행 수가 다를 수 있다. **같은 행에서만** 비교한다.
    key = ["block", "item_nm", "lead"]
    common = None
    for t in tags:
        s = set(map(tuple, runs[t][key].values))
        common = s if common is None else (common & s)
    print("=" * 70)
    print(f"[LLM 여러 회차 판정]  {len(tags)}회 · 공통 {len(common):,}행")
    print("  ※ 1차는 날짜를 알려준 오염된 회차입니다 (2026-09-01)")
    print("=" * 70)

    base = runs[tags[0]]
    base = base[[tuple(r) in common for r in base[key].values]].sort_values(key)
    act, anc, lgb = base.actual.values, base.anchor.values, base.lgbm.values
    g3 = base.lead >= 3

    preds = {}
    for t in tags:
        d = runs[t]
        d = d[[tuple(r) in common for r in d[key].values]].sort_values(key)
        preds[t] = d.llm.values

    def show(mask, title):
        print(f"\n  [{title}]  {int(mask.sum()):,}행")
        b = wm(act[mask], anc[mask])
        l = wm(act[mask], lgb[mask])
        print(f"    {'':<12}{'WMAPE':>9}{'앵커 대비':>11}")
        print(f"    {'앵커':<12}{b:>9.4f}")
        print(f"    {'LightGBM':<12}{l:>9.4f}{(1-l/b)*100:>10.1f}%")
        ws = []
        for t in tags:
            w = wm(act[mask], preds[t][mask])
            ws.append(w)
            print(f"    {'LLM ' + t:<12}{w:>9.4f}{(1-w/b)*100:>10.1f}%")
        if len(ws) > 1:
            m, sd = st.mean(ws), st.pstdev(ws)
            print(f"    {'LLM 평균':<12}{m:>9.4f}{(1-m/b)*100:>10.1f}%"
                  f"   회차편차 {sd:.4f}")
            gap = l - m
            need = 2 * sd
            mk = ("O LightGBM 보다 나음" if gap > need else
                  "X LightGBM 보다 나쁨" if -gap > need else "ㅡ 판정 불가")
            print(f"\n    LightGBM 대비  {gap:+.4f}   편차×2 {need:.4f}   → {mk}")
            gap_b = b - m
            need_b = 2 * sd
            mk2 = ("O 앵커보다 나음" if gap_b > need_b else
                   "X 앵커보다 나쁨" if -gap_b > need_b else "ㅡ 판정 불가")
            print(f"    앵커 대비      {gap_b:+.4f}   편차×2 {need_b:.4f}   → {mk2}")

    show(np.ones(len(act), bool), "전체")
    show(g3.values, "LT>=3 (운영 구간)")

    print("\n  [품목별 · LT>=3]")
    print(f"    {'품목':<6}{'앵커':>9}{'LightGBM':>10}"
          + "".join(f"{t:>9}" for t in tags) + f"{'LLM평균':>9}{'편차':>9}")
    for it in ITEMS:
        m = (base.item_nm == it).values & g3.values
        if not m.any():
            continue
        ws = [wm(act[m], preds[t][m]) for t in tags]
        print(f"    {it:<6}{wm(act[m], anc[m]):>9.4f}{wm(act[m], lgb[m]):>10.4f}"
              + "".join(f"{w:>9.4f}" for w in ws)
              + f"{st.mean(ws):>9.4f}{st.pstdev(ws):>9.4f}")

    if len(tags) > 1:
        print("\n  [회차끼리 얼마나 다른가] 같은 칸의 값 차이")
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                d = np.abs(preds[tags[i]] - preds[tags[j]]) / preds[tags[i]]
                print(f"    {tags[i]} vs {tags[j]}   평균 {d.mean()*100:>5.1f}% · "
                      f"상관 {np.corrcoef(preds[tags[i]], preds[tags[j]])[0,1]:.4f}")
    print("\n  ※ 회차편차가 이긴 폭보다 크면 '이겼다' 고 말할 수 없습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
