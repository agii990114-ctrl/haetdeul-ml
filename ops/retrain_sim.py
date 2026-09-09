# -*- coding: utf-8 -*-
"""재학습 시뮬레이션 — **일부러 못한 모델을 지금 모델 자리에 넣어 본다.**

## 왜 필요한가

지금 모델이 잘 돌고 있어서, 「후보가 이겨서 화면에 뱃지가 뜨는」 경우를
**한 번도 못 봤다.** 좋은 소식이지만 그 길이 시험이 안 된 채로 남는다.

그래서 **못한 모델을 만들어 지금 모델인 척** 두고 돌려 본다. 그러면
후보가 이기고, 화면에 비교표와 「모델 업데이트」 버튼이 나온다.

## 쓰는 법 — 세 걸음

    python ops/retrain_sim.py 상태        지금 어떤 모델이 꽂혀 있나
    python ops/retrain_sim.py 시작        못한 모델을 꽂는다
    python ops/retrain_sim.py 되돌리기     진짜 모델을 다시 꽂는다

그 사이에 이것을 돌리면 후보가 만들어지고 화면에 뜬다.

    python agent/retrain_auto.py --kinds auc --streak 1 --gap-pp 0

## ★ 이 프로그램이 지키는 것

★ **진짜 모델을 지우지 않는다.** 옆으로 옮겨 둘 뿐이다. 되돌리기는
  다시 옮겨 오는 것이고, 백업도 따로 한 벌 더 둔다.

★ **이미 시뮬레이션 중이면 또 시작하지 않는다.** 두 번 시작하면 «옆으로
  옮겨 둔 진짜 모델» 자리에 못한 모델이 덮인다. 그러면 진짜를 잃는다.

★ **내일 아침 배치 전에 되돌리라고 알린다.** 안 되돌리면 내일 예측이
  못한 모델로 나가고, 그게 매입 파트에 그대로 전달된다.

## 안전한 이유

이 프로그램은 **파일만 옮긴다.** 예측을 돌리지도, DB 에 쓰지도 않는다.
오늘 배치는 이미 돌았으므로 오늘 나간 예측은 안 바뀐다.
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")     # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "ML" / "20260824" / "ml_train_kit_2"

LIVE = KIT / "ops_auc"                       # 실제로 쓰이는 자리
WEAK = KIT / "ops_auc_weak_sim"              # 일부러 못하게 만든 것
ASIDE = KIT / "ops_auc_원본_보관_시뮬레이션"    # 진짜를 옮겨 두는 곳
BACKUP = KIT / "ops_auc_시뮬레이션전_백업"      # 한 벌 더


def _end(p: Path) -> str:
    """번들의 학습 끝 날짜. 어떤 모델이 꽂혔는지 이걸로 안다."""
    try:
        return json.loads((p / "meta.json").read_text(encoding="utf-8"))["train_end"]
    except (OSError, ValueError, KeyError):
        return "?"


def status() -> int:
    if not LIVE.is_dir():
        print("★ ops_auc 가 없습니다. 되돌리기를 돌려 주세요.")
        return 1
    end = _end(LIVE)
    sim = ASIDE.is_dir()
    print(f"지금 꽂힌 모델   ops_auc · 학습 끝 {end}")
    if sim:
        print("상태            ★ 시뮬레이션 중입니다 (못한 모델이 꽂혀 있습니다)")
        print(f"진짜 모델       {ASIDE.name} · 학습 끝 {_end(ASIDE)}")
        print("\n★ 내일 아침 09:00 배치 전에 되돌려 주세요.")
        print("   python ops/retrain_sim.py 되돌리기")
    else:
        print("상태            평소입니다 (진짜 모델이 꽂혀 있습니다)")
    return 0


def start() -> int:
    if ASIDE.is_dir():
        print("★ 이미 시뮬레이션 중입니다. 또 시작하면 진짜 모델을 잃습니다.")
        print("   먼저 되돌리기를 돌려 주세요.")
        return 1
    if not WEAK.is_dir():
        print(f"★ 못한 모델이 없습니다: {WEAK.name}")
        print("   먼저 만들어야 합니다 (아래를 ml_train_kit_2 에서 돌리세요).")
        print("   python train.py train_lead0_20260908.csv --target auc \\")
        print("     --train-start 2017-01-01 --train-end 2018-12-31 --gate-lt 0 \\")
        print("     --anchor-alpha 0.4 --fixed-iter 76 --seeds 42 43 44 45 46 \\")
        print("     --items 배추 양파 무 --quantile \\")
        print('     --quantile-q "배추=0.03,양파=0.02,무=0.03" \\')
        print("     --save-model ops_auc_weak_sim")
        return 1
    if not LIVE.is_dir():
        print("★ ops_auc 가 없습니다. 손댈 수 없습니다.")
        return 1

    #   ★ 백업을 **먼저** 한다. 옮기다 죽어도 진짜가 남아야 한다.
    if not BACKUP.is_dir():
        shutil.copytree(LIVE, BACKUP)
        print(f"백업 만듦        {BACKUP.name}")
    shutil.move(str(LIVE), str(ASIDE))       # 지우지 않고 옆으로
    shutil.copytree(WEAK, LIVE)
    print(f"진짜 모델 옮김    ops_auc -> {ASIDE.name} (학습 끝 {_end(ASIDE)})")
    print(f"못한 모델 꽂음    {WEAK.name} -> ops_auc (학습 끝 {_end(LIVE)})")
    print("\n다음을 돌리면 후보가 만들어지고 화면에 뜹니다 (1~2분).")
    print("   python agent/retrain_auto.py --kinds auc --streak 1 --gap-pp 0")
    print("\n★ 끝나면 반드시 되돌려 주세요. 내일 아침 09:00 배치 전에.")
    print("   python ops/retrain_sim.py 되돌리기")
    return 0


def restore() -> int:
    if not ASIDE.is_dir():
        print("시뮬레이션 중이 아닙니다. 되돌릴 것이 없습니다.")
        return status()
    #   지금 꽂힌 것(못한 모델이거나, 버튼을 눌러 바뀐 후보)을 옆으로 치운다
    if LIVE.is_dir():
        junk = KIT / "ops_auc_시뮬레이션결과"
        if junk.is_dir():
            shutil.rmtree(junk)
        shutil.move(str(LIVE), str(junk))
        print(f"시뮬레이션 중 꽂혀 있던 것 -> {junk.name} (학습 끝 {_end(junk)})")
    shutil.move(str(ASIDE), str(LIVE))
    print(f"진짜 모델 되돌림  ops_auc · 학습 끝 {_end(LIVE)}")
    print("\n다음도 같이 정리해 주세요 (남아 있어도 해롭지는 않습니다).")
    print("   진행기록/agent_logs/_retrain_pending.json  기다리는 결정 기록")
    return 0


#   ★ 시뮬레이션이 남기는 것들. **`ops_auc` 와 `ops_auc_weak_sim` 은 절대
#     안 넣는다** — 앞은 실제로 쓰는 모델이고, 뒤는 다음 시뮬레이션에서
#     다시 쓴다 (두면 학습 1분을 아낀다).
JUNK = (
    "ops_auc_시뮬레이션결과",
    "ops_auc_시뮬레이션전_백업",
    "ops_auc_시뮬레이션전_20260909",
    "ops_auc_교체전_20260909",
)


def clean() -> int:
    """시뮬레이션 찌꺼기를 지운다.

    ★ **시뮬레이션 중이면 안 지운다.** 그때 지우면 되돌릴 것을 잃는다.
    ★ 지울 목록을 먼저 보이고 지운다. 무엇이 사라졌는지 알아야 한다.
    """
    if ASIDE.is_dir():
        print("★ 시뮬레이션 중입니다. 먼저 되돌리기를 하세요.")
        print("   python ops/retrain_sim.py restore")
        return 1
    n = 0
    for name in JUNK:
        p = KIT / name
        if not p.is_dir():
            continue
        print(f"  지움  {name}  (학습 끝 {_end(p)})")
        shutil.rmtree(p)
        n += 1
    #   후보 번들도 치운다. 필요하면 1분이면 다시 만든다.
    for p in sorted(KIT.glob("ops_auc_cand_*")):
        print(f"  지움  {p.name}  (후보 · 필요하면 다시 만듭니다)")
        shutil.rmtree(p)
        n += 1
    print()
    print(f"{n}개 지웠습니다.")
    print(f"남긴 것  ops_auc (쓰는 모델) · {WEAK.name} (다음 시뮬레이션용)")
    return 0


GUIDE = """재학습 시뮬레이션 — 일부러 못한 모델을 «지금 모델» 자리에 넣어 봅니다.

  세 걸음                                       (윈도우면 영어 쪽을 쓰세요)

    1)  python ops/retrain_sim.py start         못한 모델을 꽂는다
    2)  python agent/retrain_auto.py --kinds auc --streak 1 --gap-pp 0
                                                후보를 만들고 견준다 (1~2분)
        -> 화면 localhost:3000/console/forecast 에 빨간 뱃지가 뜹니다
    3)  python ops/retrain_sim.py restore       ★ 진짜 모델을 되돌린다

  그 밖

    python ops/retrain_sim.py status            지금 어떤 모델이 꽂혔나
    python ops/retrain_sim.py clean             시뮬레이션 찌꺼기를 지운다

  한글로도 됩니다 — start=시작 · restore=되돌리기 · status=상태 · clean=정리

★ 내일 아침 09:00 배치 전에 반드시 3) 을 하세요. 안 하면 못한 모델로
  예측이 나가고 매입 파트에 그대로 전달됩니다.
"""


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("무엇", nargs="?", default=None)
    ap.add_argument("-h", "--help", action="store_true")
    a = ap.parse_args()
    what = getattr(a, "무엇")

    #   ★ 그냥 치면 **오류가 아니라 안내**를 낸다. 무엇을 쳐야 할지 모르는
    #     사람에게 «argument required» 라고 답하는 것은 도움이 안 된다.
    if a.help or what is None:
        print(GUIDE)
        print("-" * 62)
        return status()

    if what in ("상태", "status"):
        return status()
    if what in ("시작", "start"):
        return start()
    if what in ("되돌리기", "restore"):
        return restore()
    if what in ("정리", "clean"):
        return clean()
    print("모르는 말입니다: %s" % what)
    print()
    print(GUIDE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
