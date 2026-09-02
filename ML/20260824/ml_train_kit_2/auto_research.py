# -*- coding: utf-8 -*-
"""오토리서치 — 조절값을 밤새 스스로 찾는다 (2026-09-02)

카파시의 AutoResearch(2026-03-07) 틀을 우리 규칙에 맞게 고친 것이다.

## 무엇을 그대로 쓰고 무엇을 바꿨나

    그대로   쓰다 → 돌리다 → 재다 → 정하다 를 사람 없이 반복
             좋아지면 남기고 나빠지면 되돌린다

    바꿈 ①   점수가 WMAPE 하나가 아니라 **우리 판정 규칙**이다
    바꿈 ②   git commit/reset 대신 파일 사본 (우리 폴더는 git 저장소가 아니다)
    바꿈 ③   feature 를 못 건드린다. 조절값만 바꾼다
    바꿈 ④   LLM 이 코드를 쓰지 않는다 (아래 참조)

## ★ 바꿈 ① — 점수를 판정 규칙으로

원본은 검증 점수 하나를 올리면 채택한다. **우리 규칙을 전부 어긴다.**

    한 폴드로 결정 안 한다 (§5.7)   →  폴드 A 만 보고 채택, B 에서 뒤집힘
    품목별로 본다 (§8)              →  무가 좋아지고 양파가 나빠져도 모름
    운영이 쓰는 자리에서 잰다         →  엉뚱한 트리 수에서 재고 갈아탐

**그리고 제일 위험한 것**: `lead_biz_d` 를 빼면 통합 WMAPE 는 좋아지나
리드타임별 곡선이 평평해져 사업 가치가 사라진다 (CLAUDE.md 명시).
**점수만 보는 루프는 그걸 반드시 뺀다.** 그래서 feature 를 아예 잠근다.

## ★ 바꿈 ④ — 왜 LLM 에게 코드를 안 쓰게 하나

조절값 6개를 고르는 데는 **탐색이 LLM 보다 낫다.** 매번 같은 답이 나오고,
싸고, 무엇을 왜 골랐는지 기록이 남는다. 우리 원칙 그대로다 —
**판단은 규칙이, 설명은 도우미가.**

## ★ 탐색을 많이 하면 두 폴드에도 우연히 맞는다

100번 돌리면 그중 하나는 폴드 A·B 를 우연히 둘 다 이긴다.
**시험을 여러 번 보고 제일 잘 본 성적만 내는 것**과 같다.

    폴드 A(검증2023) · B(검증2022)   탐색에 쓴다
    폴드 C(검증2021)                **탐색에 안 쓴다.** 마지막에 한 번만 확인

C 에서도 좋아져야 채택한다. 여기서 떨어지면 그건 우연이었다는 뜻이다.

## 쓰는 법

    python auto_research.py <csv> --target auc --trials 60
    python auto_research.py <csv> --target auc --trials 200 --seeds 5   # 밤새

결과는 `실험결과/` 에만 남긴다. `prediction_log` 에 넣지 않는다.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
ITEMS = ["배추", "무", "양파"]
#   탐색에 쓰는 폴드 두 개 + 확인용 한 개
FOLDS = {"A": ("2022-12-31", "2023-12-31"),
         "B": ("2021-12-31", "2022-12-31")}
FOLD_C = ("2020-12-31", "2021-12-31")

#   ★ 탐색 공간. 우리 자료는 실질 표본이 고유 기준일 1,475개뿐이라
#   모델을 키우면 나빠진다 (실측: 50그루 0.1665 → 1200그루 0.1855).
#   그래서 위쪽을 크게 열지 않는다. 넓게 열면 대부분을 과적합 구간에서 쓴다.
SPACE = {
    "n_round": [40, 50, 60, 76, 90, 110, 130, 160, 200],
    "learning_rate": [0.02, 0.03, 0.04, 0.05, 0.07],
    "num_leaves": [7, 11, 15, 21, 31, 45, 63],
    "min_data_in_leaf": [20, 40, 60, 90, 130, 200, 300],
    "feature_fraction": [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    "bagging_fraction": [0.6, 0.7, 0.8, 0.9, 1.0],
    "lambda_l2": [0.0, 0.5, 1.0, 3.0, 10.0, 30.0],
}


def wm(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return np.abs(a - p).sum() / np.abs(a).sum()


class Data:
    """폴드별 재료를 한 번만 만들어 재사용한다. 매번 CSV 를 읽으면 느리다."""

    def __init__(self, csv, target, alpha, train_start, gate_lt):
        self.f = {}
        for tag, (tend, vend) in list(FOLDS.items()) + [("C", FOLD_C)]:
            tr, va, feats, cats, tgt, anc, label = build(csv, target, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(train_start)]
            va = va[va.lead_biz_d >= gate_lt].copy()
            self.f[tag] = dict(tr=tr, va=va, feats=feats, cats=cats,
                               tgt=tgt, anc=anc,
                               ancv=va[anc].to_numpy(float),
                               act=va[tgt].to_numpy(float),
                               mask={i: (va.item_nm == i).to_numpy() for i in ITEMS})
            self.label = label


def run_fold(d, params, n_round, seeds):
    """한 폴드에서 시드별 WMAPE 를 낸다. 통합과 품목별을 같이 돌려준다."""
    tot, per = [], {i: [] for i in ITEMS}
    for s in seeds:
        p = dict(T.PARAMS, **params, seed=s, bagging_seed=s, feature_fraction_seed=s)
        p.pop("n_round", None)
        m = lgb.train(p, lgb.Dataset(d["tr"][d["feats"]], d["tr"]["y"],
                                     categorical_feature=d["cats"]),
                      num_boost_round=n_round)
        pr = d["ancv"] * np.exp(m.predict(d["va"][d["feats"]]))
        tot.append(wm(d["act"], pr))
        for i in ITEMS:
            k = d["mask"][i]
            if k.any():
                per[i].append(wm(d["act"][k], pr[k]))
    return tot, per


def evaluate(data, cand, seeds, tags=("A", "B")):
    out = {}
    n_round = cand["n_round"]
    params = {k: v for k, v in cand.items() if k != "n_round"}
    for tag in tags:
        tot, per = run_fold(data.f[tag], params, n_round, seeds)
        out[tag] = dict(tot=tot, per=per)
    return out


def judge(base, cand, tags=("A", "B")):
    """우리 판정 규칙. 통과하면 (True, 개선폭), 아니면 (False, 이유)."""
    gains, needs = [], []
    for tag in tags:
        b, c = base[tag]["tot"], cand[tag]["tot"]
        g = st.mean(b) - st.mean(c)            # 양수면 좋아진 것
        gains.append(g)
        needs.append(2 * max(st.pstdev(b), st.pstdev(c)))
    if len({np.sign(g) for g in gains}) != 1:
        return False, "폴드 부호가 갈림 (%s)" % " · ".join("%+.4f" % g for g in gains)
    if sum(gains) <= max(needs):
        return False, "합산 %+.4f 가 편차×2 %.4f 미달" % (sum(gains), max(needs))
    if sum(gains) < 0:
        return False, "나빠짐"

    #   ★ 품목별로도 본다 (§8). 하나라도 뚜렷하게 나빠지면 안 채택한다.
    #   통합이 올라도 한 품목이 무너지면 그 품목 매입 판단이 망가진다.
    for i in ITEMS:
        ig, ineed = [], []
        for tag in tags:
            b, c = base[tag]["per"][i], cand[tag]["per"][i]
            if not b or not c:
                continue
            ig.append(st.mean(b) - st.mean(c))
            ineed.append(2 * max(st.pstdev(b), st.pstdev(c)))
        if ig and -sum(ig) > max(ineed):
            return False, "%s 가 나빠짐 (%+.4f)" % (i, sum(ig))
    return True, sum(gains)


def sample(rng, around=None, n_change=2):
    """무작위로 뽑거나, 지금 제일 좋은 것 주변을 조금만 바꾼다.

    처음에는 넓게 훑고, 좋은 게 나오면 그 근처를 판다. 조절값을 한 번에
    다 바꾸면 무엇이 효과였는지 알 수 없다.
    """
    if around is None:
        return {k: rng.choice(v) for k, v in SPACE.items()}
    c = dict(around)
    for k in rng.sample(list(SPACE), k=min(n_change, len(SPACE))):
        opts = SPACE[k]
        i = opts.index(c[k]) if c[k] in opts else rng.randrange(len(opts))
        j = max(0, min(len(opts) - 1, i + rng.choice([-2, -1, 1, 2])))
        c[k] = opts[j]
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description="조절값을 스스로 찾는다")
    ap.add_argument("csv")
    ap.add_argument("--target", default="auc", choices=list(OPS))
    ap.add_argument("--trials", type=int, default=60)
    ap.add_argument("--seeds", type=int, default=5, help="한 번 잴 때 시드 수")
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7, help="탐색 자체의 난수")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rng = random.Random(a.seed)
    seeds = list(range(42, 42 + a.seeds))
    alpha, ops_round = OPS[a.target]
    out = Path(a.out or f"../../../실험결과/autoresearch_{a.target}_20260902.csv")

    print("=" * 78)
    print("[오토리서치] 조절값만 찾습니다. feature 는 잠겨 있습니다")
    print(f"  타겟 {a.target} · 앵커 α={alpha} · 시드 {a.seeds}개 · 시도 {a.trials}회")
    print("  탐색 폴드 A(검증2023) · B(검증2022)   |   확인 폴드 C(검증2021) — 마지막에 한 번만")
    print("=" * 78)

    t0 = time.time()
    data = Data(a.csv, a.target, alpha, a.train_start, a.gate_lt)
    print(f"  재료 준비 {time.time()-t0:.0f}초")

    #   출발점 = 지금 운영 설정
    start = {k: T.PARAMS[k] for k in SPACE if k in T.PARAMS}
    start["n_round"] = ops_round
    base = evaluate(data, start, seeds)
    b_show = " · ".join("%s %.4f" % (t, st.mean(base[t]["tot"])) for t in FOLDS)
    print(f"\n  [지금 설정] {b_show}")
    print("  " + json.dumps(start, ensure_ascii=False))

    best, best_ev, best_gain = dict(start), base, 0.0
    rows, kept = [], 0
    for t in range(1, a.trials + 1):
        #   앞의 3분의 1은 넓게 훑고, 그 뒤로는 제일 좋은 것 주변을 판다
        cand = sample(rng, None if t <= a.trials // 3 else best)
        if cand == best:
            continue
        ev = evaluate(data, cand, seeds)
        ok, info = judge(best_ev, ev)
        gA, gB = (st.mean(best_ev[x]["tot"]) - st.mean(ev[x]["tot"]) for x in ("A", "B"))
        rows.append(dict(trial=t, **cand, foldA=st.mean(ev["A"]["tot"]),
                         foldB=st.mean(ev["B"]["tot"]), gainA=gA, gainB=gB,
                         kept=bool(ok), why=("" if ok else info)))
        if ok:
            kept += 1
            best, best_ev = dict(cand), ev
            best_gain += info
            print(f"  [{t:3d}] ★ 채택  A {st.mean(ev['A']['tot']):.4f} · "
                  f"B {st.mean(ev['B']['tot']):.4f}  (합산 {info:+.4f})")
            print("        " + json.dumps(cand, ensure_ascii=False))
        elif t % 10 == 0:
            print(f"  [{t:3d}] … 진행 중 (채택 {kept}회 · {time.time()-t0:.0f}초)")

    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n  시도 {len(rows)}회 · 채택 {kept}회 · {time.time()-t0:.0f}초 → {out}")

    if kept == 0:
        print("\n  ── 결론 ──")
        print("  바꿀 만한 것을 못 찾았습니다. **지금 설정이 이미 좋다는 뜻입니다.**")
        print("  '안 해봤다' 가 아니라 '훑어봤고 지금이 최선이더라' 가 됐습니다.")
        return 0

    # ── 확인 폴드 C ────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("[확인] 탐색에 안 쓴 폴드 C(검증2021)에서 다시 잽니다")
    print("  탐색을 많이 하면 두 폴드에는 우연히 맞는 것이 나옵니다.")
    print("  여기서 떨어지면 그건 우연이었다는 뜻입니다.")
    print("=" * 78)
    cb = evaluate(data, start, seeds, tags=("C",))
    cc = evaluate(data, best, seeds, tags=("C",))
    g = st.mean(cb["C"]["tot"]) - st.mean(cc["C"]["tot"])
    need = 2 * max(st.pstdev(cb["C"]["tot"]), st.pstdev(cc["C"]["tot"]))
    print(f"  지금 설정 {st.mean(cb['C']['tot']):.4f}  →  찾은 설정 "
          f"{st.mean(cc['C']['tot']):.4f}   ({g:+.4f} · 필요 {need:.4f})")
    print(f"  {'  품목':<8}{'지금':>10}{'찾은 것':>10}{'개선':>10}")
    for i in ITEMS:
        b, c = cb["C"]["per"][i], cc["C"]["per"][i]
        if b and c:
            print(f"  {i:<8}{st.mean(b):>10.4f}{st.mean(c):>10.4f}"
                  f"{st.mean(b)-st.mean(c):>+10.4f}")

    print("\n  ── 결론 ──")
    if g > need:
        print("  ✅ 확인 폴드에서도 좋아졌습니다. **채택 후보입니다.**")
    elif g > 0:
        print("  ㅡ 좋아졌지만 편차×2 에 미달합니다. 시드를 늘려 다시 재세요.")
    else:
        print("  ❌ 확인 폴드에서 나빠졌습니다. **탐색 폴드에 맞춘 것입니다.**")
        print("     채택하지 마세요. 이게 이 확인 절차를 둔 이유입니다.")
    print("\n  찾은 설정: " + json.dumps(best, ensure_ascii=False))
    print("  ※ 채택하려면 train.py 의 PARAMS 와 --fixed-iter 를 바꾸고,")
    print("    세 타겟을 다시 학습해 밴드까지 새로 만들어야 합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
