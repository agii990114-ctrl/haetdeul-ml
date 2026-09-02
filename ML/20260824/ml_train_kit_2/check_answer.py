# -*- coding: utf-8 -*-
"""LLM 답이 망가졌는지 검사한다 (2026-09-02)

## 왜 필요한가

2026-09-02 에 배추 27블록을 한 번에 시켰더니 **블록마다 새로 답한 게 아니라
하나의 긴 숫자 줄을 2칸씩 밀어가며 잘라 썼습니다.** 그걸 모르고 채점하면
"성적이 나빴다" 로 기록됩니다 — 사실은 답이 아니었는데요.

**채점 전에 항상 이 검사를 먼저 합니다.**

## 무엇을 보나

    1  밀어쓰기   앞 블록을 k칸 밀면 뒤 블록과 같아지나
    2  출발점     첫 칸이 그 블록의 출발점에서 너무 멀지 않나
    3  톱니       하루하루 변화가 실제 가격보다 심하게 튀지 않나
    4  개수       블록 수와 칸 수가 맞나
"""
from __future__ import annotations

import argparse
import re
import statistics as st
import sys
from pathlib import Path

import pandas as pd


def read(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip().strip("`")
        if "|" not in line:
            continue
        b, rest = line.split("|", 1)
        try:
            v = [float(x.replace(",", "").strip()) for x in rest.split(",")]
        except ValueError:
            continue
        if len(v) >= 5:
            out[b.strip()] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM 답이 망가졌는지 본다")
    ap.add_argument("answer")
    ap.add_argument("--key", default=None, help="정답 키 CSV (출발점 대조용)")
    ap.add_argument("--csv", default=None, help="학습 CSV (출발점 대조용)")
    a = ap.parse_args()

    got = read(a.answer)
    ids = sorted(got, key=lambda x: int(re.sub(r"\D", "", x) or 0))
    print("=" * 66)
    print(f"[답 검사] {Path(a.answer).name} · 블록 {len(got)}개")
    print("=" * 66)
    bad = 0

    # 1 ── 밀어쓰기
    hits = []
    for i in range(len(ids) - 1):
        x, y = got[ids[i]], got[ids[i + 1]]
        for k in range(1, 6):
            if len(x) > k and x[k:k + len(y)] == y[:len(x) - k] and len(x) - k >= 8:
                hits.append((ids[i], ids[i + 1], k))
                break
    if hits:
        bad += 1
        print(f"\n  ✗ 밀어쓰기 {len(hits)}쌍 — **채점하면 안 됩니다**")
        for p, q, k in hits[:6]:
            print(f"      {p} 를 {k}칸 밀면 {q} 와 같습니다")
    else:
        print("\n  ✓ 밀어쓰기 없음")

    # 2 ── 톱니
    rough = []
    for b in ids:
        v = got[b]
        ch = [abs(v[i + 1] - v[i]) / v[i] * 100 for i in range(len(v) - 1) if v[i]]
        if ch and st.mean(ch) > 12:
            rough.append((b, st.mean(ch)))
    if rough:
        bad += 1
        print(f"\n  ✗ 하루 변화가 심한 블록 {len(rough)}개 (평균 12% 초과)")
        for b, m in rough[:6]:
            print(f"      {b}  평균 {m:.1f}%")
        print("      실제 경락가는 보통 하루 5~10% 움직입니다")
    else:
        print("  ✓ 하루 변화 정상")

    # 3 ── 출발점에서 얼마나 떨어져 시작하나
    if a.key and a.csv:
        k = pd.read_csv(a.key, encoding="utf-8-sig", parse_dates=["base_dt"])
        d = pd.read_csv(a.csv, encoding="utf-8-sig", parse_dates=["base_dt"],
                        usecols=["base_dt", "item_nm", "lead_biz_d",
                                 "auc_prc_lag1", "auc_prc_avg7"])
        d = d[d.lead_biz_d == 1]
        far = []
        for _, r in k.iterrows():
            if r.block not in got:
                continue
            g = d[(d.base_dt == r.base_dt) & (d.item_nm == r.item_nm)]
            if g.empty or pd.isna(g.auc_prc_lag1.iloc[0]):
                continue
            anc = 0.4 * g.auc_prc_lag1.iloc[0] + 0.6 * g.auc_prc_avg7.iloc[0]
            gap = abs(got[r.block][0] - anc) / anc * 100
            if gap > 25:
                far.append((r.block, gap))
        if far:
            bad += 1
            print(f"\n  ✗ 첫 칸이 출발점에서 25% 넘게 떨어진 블록 {len(far)}개")
            for b, gp in far[:6]:
                print(f"      {b}  {gp:.0f}% 차이")
        else:
            print("  ✓ 첫 칸이 출발점 근처")

    print()
    print("  → " + ("채점해도 됩니다" if bad == 0 else
                    "★ 답이 망가졌습니다. 다시 받으세요"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
