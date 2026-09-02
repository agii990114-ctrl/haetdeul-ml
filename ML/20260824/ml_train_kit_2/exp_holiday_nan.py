# -*- coding: utf-8 -*-
"""holiday_remain_d 를 무 행에서만 비운다 — 실제 성능 확인 (2026-09-01)

## 무엇을 하나

`holiday_remain_d`(명절까지 며칠)가 **품목마다 반대로 작용한다.**
시드 두 벌(42~61 · 62~81)로 확인했고 18칸 중 17칸이 같은 부호였다.

    무     6/6 칸에서 빼는 게 낫다
    양파   1/6 칸만 그렇다 = 있어야 한다
    배추   3/6 으로 갈린다

**그래서 "빼기/두기" 가 답이 아니다.** 단일 모델을 유지하면서 품목별로
다르게 주는 방법은 **무 행에서만 결측으로 두는 것**이다.

## 왜 지우지 않고 비우나

LightGBM 은 결측을 "값이 없다" 로 따로 취급한다. 0 이나 -1 로 채우면
**"명절이 코앞" 이라는 뜻**이 되어 오히려 틀린 신호를 준다.

## 왜 무만 다를까 (가설 — 확인 안 함)

무는 산지가 계절마다 통째로 바뀐다 (겨울 제주 · 여름 고랭지).
그 전환기가 명절 시기와 겹친다. 모델이 "명절까지 며칠" 을 보고
**명절 효과가 아니라 산지 전환을 배웠을** 수 있다.

## 판정

§5.7 2폴드 + §8 품목별. **통합값만 보지 않는다** — 무가 좋아지고
양파가 나빠지면 통합은 안 움직일 수 있다.
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train as T                                            # noqa: E402
from exp_quantile import build                               # noqa: E402

OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
FOLDS = [("A(2023)", "2022-12-31", "2023-12-31"),
         ("B(2022)", "2021-12-31", "2022-12-31")]
COL = "holiday_remain_d"
ITEMS = ["배추", "무", "양파"]


def wm(a, p):
    return np.abs(a - p).sum() / np.abs(a).sum()


def blank_for(df, items):
    """지정한 품목의 행에서만 COL 을 비운다. 원본은 안 건드린다."""
    d = df.copy()
    m = d["item_nm"].astype(str).isin(items)
    d.loc[m, COL] = np.nan
    return d


def run(tr, va, feats, cats, tgt, anc, rounds, seeds):
    ancv, act = va[anc].to_numpy(float), va[tgt].to_numpy(float)
    per = {it: [] for it in ITEMS}
    tot = []
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"], categorical_feature=cats),
                      num_boost_round=rounds)
        pr = ancv * np.exp(m.predict(va[feats]))
        tot.append(wm(act, pr))
        for it in ITEMS:
            k = (va.item_nm == it).to_numpy()
            if k.any():
                per[it].append(wm(act[k], pr[k]))
    return tot, per


def main() -> int:
    ap = argparse.ArgumentParser(description="무 행에서만 명절 feature 를 비운다")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--blank", nargs="+", default=["무"], help="비울 품목")
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(42, 62)))
    a = ap.parse_args()

    print("=" * 76)
    print("[명절 feature 품목별 처리] %s 행에서만 %s 를 비운다" % (a.blank, COL))
    print("  시드 %d개 · LT>=3 · 운영 조건(수축 앵커 · 고정 트리)" % len(a.seeds))
    print("=" * 76)

    verdict = {}
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        for tag, tend, vend in FOLDS:
            tr, va, feats, cats, tgt, anc, label = build(a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp("2017-01-01")]
            va = va[va.lead_biz_d >= 3].copy()
            if COL not in feats:
                print("  %s: %s 가 입력에 없습니다" % (label, COL))
                break
            #   ★ 학습과 검증 **양쪽 다** 비운다. 한쪽만 비우면 운영에서
            #   본 적 없는 형태가 들어와 조용히 어긋난다.
            t0, p0 = run(tr, va, feats, cats, tgt, anc, rounds, a.seeds)
            t1, p1 = run(blank_for(tr, a.blank), blank_for(va, a.blank),
                         feats, cats, tgt, anc, rounds, a.seeds)

            print("\n  [%s · 폴드 %s]" % (label, tag))
            print("    %-6s%11s%11s%11s%10s  %s"
                  % ("", "지금", "비운 뒤", "개선", "편차×2", "판정"))
            for nm, x, y in [("전체", t0, t1)] + [(i, p0[i], p1[i]) for i in ITEMS]:
                gain = st.mean(x) - st.mean(y)      # 양수면 비우는 게 낫다
                sd2 = 2 * max(st.pstdev(x), st.pstdev(y))
                mk = "O 좋아짐" if gain > sd2 else ("X 나빠짐" if -gain > sd2 else "ㅡ")
                print("    %-6s%11.4f%11.4f%+11.4f%10.4f  %s"
                      % (nm, st.mean(x), st.mean(y), gain, sd2, mk))
                verdict.setdefault((kind, nm), []).append((gain, sd2))

    print("\n" + "=" * 76)
    print("[2폴드 판정] 부호가 같고 합산이 편차×2 를 넘을 때만 (§5.7)")
    print("=" * 76)
    print("  %-8s%-6s%11s%11s%11s%10s  %s"
          % ("타겟", "품목", "폴드A", "폴드B", "합산", "필요", "결론"))
    for (kind, nm), rs in verdict.items():
        if len(rs) < 2:
            continue
        tot = sum(r[0] for r in rs)
        need = max(r[1] for r in rs)
        same = len({np.sign(r[0]) for r in rs}) == 1
        v = ("비우자" if (same and tot > need)
             else "두자" if (same and -tot > need) else "판정 불가")
        print("  %-8s%-6s%+11.4f%+11.4f%+11.4f%10.4f  %s"
              % (kind, nm, rs[0][0], rs[1][0], tot, need, v))
    print("\n  ※ 통합값만 보지 마세요 — 무가 좋아지고 양파가 나빠지면")
    print("    통합은 안 움직일 수 있습니다 (§8)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
