# -*- coding: utf-8 -*-
"""ablation 재판정 — 운영 조건으로 (2026-09-01)

## 왜 다시 하나

지금 쓰는 feature 목록은 **2026-08-24 ablation 2차**의 결론("변경 없음")이다.
그런데 그 뒤로 **세 가지가 바뀌었다.**

    2026-08-24  ablation 2차 실행   crop_price_train_202608241210.csv
    2026-08-27  경락가 규격 고정     ← 3일 뒤
    2026-08-28  앵커 수축 도입       ← 4일 뒤
    2026-09-01  트리 개수 실측       ← 오늘

**① 경락가 타겟이 그때는 거의 무작위였다.** 규격이 섞여 있어 배추 경락가의
자기상관 ACF(1) 이 0.085 였다 (규격 고정 후 0.795). CLAUDE.md 의 표현대로
"예측할 수 없는 값을 타겟으로 삼고 있었고, 어떤 feature 를 넣어도 나아질 수
없었" 다. **그러면 "변경 없음" 은 "무작위는 아무도 못 맞힌다" 였을 수 있다.**

**② 앵커가 바뀌었다.** 우리는 `log(타겟/앵커)` 를 배운다. ablation 때는
앵커가 어제값 하나였고 지금은 어제값과 최근 7일 평균을 섞은 값이다.
**배우는 문제 자체가 달라졌다.**

**③ 트리 개수가 다르다.** ablation 은 조기종료(best_iter 34~814 로 흔들림),
운영은 고정이다. 오늘 실측에서 50그루 0.1665 → 1200그루 0.1855 로 11% 벌어졌다.
**모델 종류를 바꾼 것(1%)보다 10배 큰 차이다.**

## 운영 조건 (ops_*/meta.json 실측)

    경락가   α=0.4 · 76그루      중도매가 α=0.8 · 122그루
    소매가   α=1.0 · 81그루      셋 다 학습 2017~ · LT 게이트 3

`ablation.py` 는 이 조건들을 못 받는다(수축 앵커·고정 트리 옵션이 없다).
그래서 오늘 검증한 `exp_quantile.build()` 를 그대로 쓴다 — train.py 와
같은 재료를 만든다는 것이 이미 확인된 함수다.

## 방법

**LOO(하나씩 빼기).** 전체에서 그룹 하나를 빼고 학습해 전체와 비교한다.

    손실 = (뺐을 때 WMAPE) − (전체 WMAPE)
    양수면 그 그룹이 기여한다는 뜻 (빼니까 나빠졌다)

## 판정 (§5.7)

폴드 두 개(검증 2023 · 검증 2022)에서 **부호가 같고** 합산이 편차×2 를
넘을 때만 바꾼다. 한 폴드로 결정하지 않는다.

    O   빼면 나빠짐 → 기여함. 유지
    X   빼면 좋아짐 → 해로움. 제거 후보
    ㅡ   판정 불가. **"기여 없음" 이 아니라 "증명 못 함" 이다** (§11)

## 쓰는 법

    python ablation_ops.py <csv>                       # 세 타겟 · 2폴드
    python ablation_ops.py <csv> --targets auc --seeds 42 43 44

결과는 `실험결과/` 에만 남긴다. `prediction_log` 에 넣지 않는다.
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
from ablation import GROUPS                                  # noqa: E402
from exp_quantile import build                               # noqa: E402

#   ops_*/meta.json 에서 읽은 실제 운영값이다. 모델을 재학습하면 같이 고쳐야 한다.
OPS = {"auc": (0.4, 76), "whsl": (0.8, 122), "rtl": (1.0, 81)}
FOLDS = [("A(검증2023)", "2022-12-31", "2023-12-31"),
         ("B(검증2022)", "2021-12-31", "2022-12-31")]

#   ★ calendar 를 통째로 빼는 판정은 쓸 수 없다. 그 안에 lead_biz_d
#   (며칠 뒤인가)가 들어 있어, 빼면 모델이 '내일' 과 '3주 뒤' 를 구분하지
#   못한다. 우리 문제의 뼈대다. 그래서 --split 으로 쪼개 어느 것이 범인인지
#   가린다. 각 조각은 성격이 다르다.
SPLIT = {
    "cal_lead": ["lead_biz_d"],                      # 며칠 뒤인가 — 뼈대
    "cal_dow": ["target_dow"],                       # 대상일 요일
    "cal_holiday": ["holiday_remain_d", "market_closed_lag1_yn"],
    "cal_kimchi": ["kimchi_season_yn"],              # 김장철 예/아니오
    "cal_mkt_temp": ["market_temp_avg_lag1"],        # 시장 소재지 기온
}

#   cal_holiday 가 중도매가에서 제거 후보로 나왔으나 아슬아슬했다
#   (합산 −0.0044 · 필요 0.0043 — 1.02배). 둘 중 어느 쪽이 범인인지
#   갈라 본다. 성격이 다르다 — 하나는 앞을 보고 하나는 뒤를 본다.
SPLIT2 = {
    "cal_hol_remain": ["holiday_remain_d"],          # 명절까지 며칠 (앞)
    "cal_hol_closed": ["market_closed_lag1_yn"],     # 어제 휴장이었나 (뒤)
}


def wmape(a, p):
    a, p = np.asarray(a, float), np.asarray(p, float)
    return np.abs(a - p).sum() / np.abs(a).sum()


def fit(tr, va, feats, cats, seeds, rounds, tgt, anc):
    ancv, actual = va[anc].to_numpy(float), va[tgt].to_numpy(float)
    ws = []
    for s in seeds:
        p = dict(T.PARAMS, seed=s, bagging_seed=s, feature_fraction_seed=s)
        m = lgb.train(p, lgb.Dataset(tr[feats], tr["y"],
                                     categorical_feature=[c for c in cats if c in feats]),
                      num_boost_round=rounds)
        ws.append(wmape(actual, ancv * np.exp(m.predict(va[feats]))))
    return st.mean(ws), (st.pstdev(ws) if len(ws) > 1 else 0.0)


def groups_for(feats, anc, split=False):
    """그룹 정의를 실제 feature 목록에 맞춘다.

    앵커를 수축하면 원본 컬럼(예: auc_prc_lag1)이 사라지고 `_anchor_mix` 가
    생긴다. 그래서 그룹 정의를 그대로 쓰면 **없는 컬럼을 빼는** 헛일이 된다.
    실제로 있는 것만 남기고, `_anchor_mix` 는 그 타겟의 가격 계열 그룹에 넣는다.
    """
    src = dict(GROUPS)
    if split:
        #   통째 calendar 를 조각으로 갈아끼운다. 합쳐서 원래와 같은 집합이다.
        src.pop("calendar", None)
        src.update(SPLIT)
    if split == "deep":
        #   cal_holiday 를 한 번 더 쪼갠다.
        src.pop("cal_holiday", None)
        src.update(SPLIT2)
    out = {}
    for g, cols in src.items():
        have = [c for c in cols if c in feats]
        if have:
            out[g] = have
    if anc == "_anchor_mix":
        #   수축 앵커는 원본 lag1 자리를 대신한다. lag1 이 어느 그룹에
        #   있었는지 찾아 거기에 넣는다.
        for g, cols in GROUPS.items():
            if any(c.endswith("_prc_lag1") for c in cols) and g in out:
                pass
        # 어느 그룹인지는 타겟마다 다르므로 별도 그룹으로 둔다 — 섞으면
        # "lag 를 뺐다" 는 말의 뜻이 타겟마다 달라진다.
        out["anchor_mix"] = ["_anchor_mix"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="운영 조건으로 ablation 을 다시 잰다")
    ap.add_argument("csv")
    ap.add_argument("--targets", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--train-start", default="2017-01-01")
    ap.add_argument("--seeds", nargs="+", type=int,
                    default=[42, 43, 44, 45, 46, 47, 48, 49, 50, 51])
    ap.add_argument("--gate-lt", type=int, default=3)
    ap.add_argument("--split", nargs="?", const=True, default=False,
                    choices=[True, "deep"],
                    help="calendar 를 조각낸다. 'deep' 이면 cal_holiday 도 한 번 더")
    ap.add_argument("--out", default=None, help="CSV 로도 남긴다")
    a = ap.parse_args()

    print("=" * 84)
    print("[ablation 재판정] 운영 조건 · 규격 고정 타겟 · 수축 앵커 · 고정 트리")
    print(f"  시드 {len(a.seeds)}개 · LT>={a.gate_lt} · LOO(하나씩 빼기)")
    print("  ※ 2026-08-24 판정은 규격 혼합 타겟 · 어제값 앵커 · 조기종료였습니다")
    print("=" * 84)

    rows = []
    for kind in a.targets:
        alpha, rounds = OPS[kind]
        per = {}
        for tag, tend, vend in FOLDS:
            tr, va, feats, cats, tgt, anc, label = build(
                a.csv, kind, tend, vend, alpha)
            tr = tr[tr.base_dt >= pd.Timestamp(a.train_start)]
            va = va[va.lead_biz_d >= a.gate_lt].copy()
            gs = groups_for(feats, anc, a.split)

            full, sd_full = fit(tr, va, feats, cats, a.seeds, rounds, tgt, anc)
            print(f"\n  [{label} · 폴드 {tag}]  α={alpha} · {rounds}그루 · "
                  f"feature {len(feats)}개 · 검증 {len(va):,}행")
            print(f"    전체 {full:.4f} (시드편차 {sd_full:.4f})")
            print(f"    {'뺀 그룹':<14}{'컬럼':>5}{'WMAPE':>9}{'손실':>10}"
                  f"{'편차×2':>9}  판정")
            for g, cols in gs.items():
                keep = [c for c in feats if c not in cols]
                w, sd = fit(tr, va, keep, cats, a.seeds, rounds, tgt, anc)
                loss = w - full                       # 양수면 기여함
                sd2 = 2 * max(sd, sd_full)
                mk = "O" if loss > sd2 else ("X" if -loss > sd2 else "ㅡ")
                per.setdefault(g, []).append((loss, sd2))
                print(f"    {g:<14}{len(cols):>5}{w:>9.4f}{loss:>+10.4f}"
                      f"{sd2:>9.4f}  {mk}")

        print(f"\n  ── {label} 2폴드 판정 ──")
        print(f"    {'그룹':<14}{'폴드A':>10}{'폴드B':>10}{'합산':>10}"
              f"{'필요':>9}  결론")
        for g, rs in per.items():
            tot = sum(r[0] for r in rs)
            need = max(r[1] for r in rs)
            same = len({np.sign(r[0]) for r in rs}) == 1
            verd = ("유지(기여함)" if (same and tot > need)
                    else "제거 후보" if (same and -tot > need) else "판정 불가")
            print(f"    {g:<14}{rs[0][0]:>+10.4f}{rs[1][0]:>+10.4f}"
                  f"{tot:>+10.4f}{need:>9.4f}  {verd}")
            rows.append(dict(target=kind, label=label, group=g,
                             loss_A=rs[0][0], loss_B=rs[1][0],
                             total=tot, need=need, verdict=verd))

    print("\n" + "=" * 84)
    print("  ※ 'ㅡ 판정 불가' 는 기여가 없다는 뜻이 아니라 증명 못 했다는 뜻입니다 (§11)")
    print("  ※ 폴드가 갈리면 그해에 무슨 일이 있었는지 보세요 —")
    print("    폴드 B 의 검증 2022 에는 태풍 힌남노(9/6)가 들어 있습니다")
    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[저장] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
