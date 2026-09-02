# -*- coding: utf-8 -*-
"""분위수 밴드 운영 교체 (2026-09-02)

## 무엇을 하나

`ops_auc` · `ops_whsl` 번들을 분위수 모델이 든 것으로 **같은 이름으로** 바꾼다.

    ops_auc      →  ops_auc_교체전_YYYYMMDD   (백업)
    ops_auc_q    →  ops_auc                   (승격)

## ★ 왜 이름을 안 바꾸나

매입 파트 필터가 **정확히 일치**만 받는다.

    model_ver = ANY('ops_auc', 'ops_whsl', 'ops_rtl')

이름을 바꾸면 저쪽에서 **에러 없이 0건**이 된다. 2026-09-01 사고와 같은
종류다 — 모델 이름 한 글자 차이(밑줄 vs 붙임표)로 다른 계열이 섞였는데
아무도 몰랐다. (`context/20260901/1.txt` 에서 매입 파트가 확인해 줬다)

## ★ 대신 반드시 할 것

이름이 같으면 `prediction_log` 에서 **교체 전후 구간이 섞인다.**
`pred_prc`(예측 가격)는 안 바뀌지만 `pred_lo`/`pred_hi`(구간)는 만드는
방법이 달라진다.

    · 교체 날짜를 CLAUDE.md 와 회신 문서에 못박는다
    · 매입 파트에 **미리** 알린다

## 무엇이 바뀌고 안 바뀌나

    안 바뀜   pred_prc · model_ver · 컬럼 계약 · 저쪽 코드
    바뀜      pred_lo / pred_hi 를 만드는 방법
              고정표(품목×리드타임) → 분위수 회귀(그날 상황 반영)

## 되돌리기

    python cutover_quantile.py --rollback

## 쓰는 법

    python cutover_quantile.py --check       # 무엇이 바뀌는지만 본다
    python cutover_quantile.py --commit      # 실제로 교체
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = [("ops_auc", "ops_auc_q"), ("ops_whsl", "ops_whsl_q")]
STAMP = datetime.date.today().strftime("%Y%m%d")


def info(d: Path):
    m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    q = m.get("quantile_models") or {}
    return dict(models=len(m["models"]), band=len(m.get("band") or {}),
                q=len(q), qmap=m.get("quantile_q"),
                iters=m.get("fixed_iter"), alpha=m.get("anchor_alpha"),
                created=m.get("created_at"))


def main() -> int:
    ap = argparse.ArgumentParser(description="분위수 밴드로 운영 번들을 교체한다")
    ap.add_argument("--commit", action="store_true", help="실제로 교체한다")
    ap.add_argument("--rollback", action="store_true", help="되돌린다")
    a = ap.parse_args()

    if a.rollback:
        n = 0
        for live, _ in PAIRS:
            baks = sorted(HERE.glob(f"{live}_교체전_*"))
            if not baks:
                print(f"  {live}: 백업이 없습니다")
                continue
            bak = baks[-1]
            cur = HERE / live
            if cur.exists():
                shutil.rmtree(cur / "_tmp", ignore_errors=True)
                shutil.move(str(cur), str(HERE / f"{live}_되돌리기전_{STAMP}"))
            shutil.move(str(bak), str(cur))
            print(f"  {live} ← {bak.name} 로 되돌렸습니다")
            n += 1
        print(f"\n되돌린 번들 {n}개. **배치를 다시 돌려 확인하세요.**")
        return 0

    print("=" * 70)
    print("[분위수 밴드 운영 교체]")
    print("=" * 70)
    ok = True
    for live, new in PAIRS:
        dl, dn = HERE / live, HERE / new
        if not dn.exists():
            print(f"  ✗ {new} 가 없습니다")
            ok = False
            continue
        a1, b1 = info(dl), info(dn)
        print(f"\n  {live}")
        print(f"    지금  점예측 {a1['models']}개 · 분위수 {a1['q']}수준 · "
              f"밴드 {a1['band']}조합 · iter {a1['iters']} · α {a1['alpha']}")
        print(f"    바꿈  점예측 {b1['models']}개 · 분위수 {b1['q']}수준 · "
              f"밴드 {b1['band']}조합 · iter {b1['iters']} · α {b1['alpha']}")
        #   ★ 점 예측이 달라지면 안 된다. 학습 조건이 같아야 같은 값이 나온다.
        for k in ("models", "iters", "alpha"):
            if a1[k] != b1[k]:
                print(f"    ✗ {k} 가 다릅니다 ({a1[k]} → {b1[k]}). "
                      "점 예측이 달라집니다 — 교체하면 안 됩니다")
                ok = False
        if b1["q"] == 0:
            print("    ✗ 새 번들에 분위수 모델이 없습니다")
            ok = False
        if b1["band"] == 0:
            print("    ✗ 새 번들에 고정표가 없습니다 (되돌릴 수 없게 됩니다)")
            ok = False
        print(f"    품목별 q  {b1['qmap']}")

    print("\n" + "-" * 70)
    if not ok:
        print("  ★ 위 문제를 고치기 전에는 교체하지 마세요.")
        return 1
    print("  ✓ 검사 통과")
    print("\n  바뀌는 것   pred_lo / pred_hi 를 만드는 방법")
    print("  안 바뀌는 것 pred_prc · model_ver · 컬럼 계약 · 매입 파트 코드")
    print("\n  ★ 교체 전에 반드시:")
    print("     1. 매입 파트에 교체 날짜를 미리 알릴 것")
    print("     2. 그 날짜를 CLAUDE.md 와 회신 문서에 적을 것")
    print("        (같은 이름이라 표에서 교체 전후가 섞입니다)")

    if not a.commit:
        print("\n  --commit 이 없어 실제로 바꾸지 않았습니다.")
        return 0

    for live, new in PAIRS:
        dl, dn = HERE / live, HERE / new
        bak = HERE / f"{live}_교체전_{STAMP}"
        if bak.exists():
            shutil.rmtree(bak)
        shutil.move(str(dl), str(bak))
        shutil.copytree(str(dn), str(dl))     # 원본(_q)은 남겨 둔다
        print(f"  {live}  ←  {new}   (백업 {bak.name})")
    print("\n  교체 완료. **배치 predict 단계를 돌려 확인하세요.**")
    print("  되돌리려면  python cutover_quantile.py --rollback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
