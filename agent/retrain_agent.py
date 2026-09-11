#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""재학습 agent — **다시 배워야 하나**를 판정하고, 판정만 한다.

    스프린트 4 의 ②③ 입니다.
        ① 오차가 기준선을 N주 연속 초과하면 알림      -> drift_agent (완료)
        ② 재학습 트리거가 기록에 남음                -> 이 파일
        ③ 새 모델이 검증을 통과 못 하면 교체 안 됨     -> retrain_build.py

    ★ 자동으로 재학습하지 않습니다. 자동으로 교체하지 않습니다.

        성능이 나빠졌다는 것은 **시장이 이상하다**는 뜻일 수도 있습니다.
        그때 그 구간을 그대로 배우면 이상한 시장을 정답으로 배웁니다.
        폴드 B(2022 · 태풍 힌남노)가 실험 다섯 건에서 혼자 반대 부호를 냈던
        것이 그 모양이었습니다.

        그래서 이 agent 는 **후보를 만들 이유가 있는지까지만** 말합니다.
        만드는 것은 사람이 `retrain_build.py` 를 부릅니다.

    ★ 경락가만 판정합니다.

        매입 파트 코드가 `target_kind = 'AUC'` 로 못 박고 읽습니다
        (`backend/app/master/inputs.py:127`). 중도매가·소매가는 화면에서
        골라 볼 수만 있고 판단에 안 들어갑니다.

        **감시는 셋 다 합니다** (drift_agent 그대로). 기록이 남아야 파는 쪽이
        생겼을 때 씁니다. 여기서 `--kinds` 를 풀면 셋 다 판정합니다.

    두 가지를 봅니다.

        ㄱ 밀림   앵커 대비 STREAK 주 연속으로 뒤진다          -> drift 와 같은 규칙
        ㄴ 낡음   학습이 끝난 날로부터 너무 오래 지났다

        ★ 둘은 성격이 다릅니다. 밀림은 "지금 나쁘다", 낡음은 "나쁠 수 있다"
          입니다. 낡음만으로 재학습을 권하지 않습니다 — 데이터를 더 준다고
          좋아지지 않는다는 것을 실측했기 때문입니다 (학습 시작 2015 -> 2017
          로 줄이니 +5.9% -> +6.8%).

    쓰는 법
        python agent/retrain_agent.py
        python agent/retrain_agent.py --kinds auc whsl rtl
        python agent/retrain_agent.py --save
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import db, Finding, Report, OK, WARN, BAD           # noqa: E402
from drift_agent import SQL, MIN_ROWS, GAP_PP, STREAK, BASE_WEEKS, SKIP_KINDS   # noqa: E402

#   ★ 자기 출력을 UTF-8 로 고정한다 (2026-09-07).
#
#     윈도우 기본이 cp949 라, 보고서에 '—'(em dash) 하나만 있어도
#     UnicodeEncodeError 로 죽는다. 사람이 터미널에서 돌릴 때는
#     PYTHONIOENCODING=utf-8 을 붙여 왔지만, **화면에서 부르면 그게
#     안 넘어온다.** 부모에게 기대지 않고 여기서 직접 고정한다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")   # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "ML" / "20260824" / "ml_train_kit_2"

#: 운영 번들 이름. 이름은 매입 파트 필터가 정확히 일치로 걸어서 못 바꿉니다.
BUNDLE = {"auc": "ops_auc", "whsl": "ops_whsl", "rtl": "ops_rtl"}

#: 판정 대상. 기본은 경락가 하나 — 저쪽이 실제로 읽는 것이 그것뿐입니다.
DEFAULT_KINDS = ["auc"]

#: 학습이 끝난 날로부터 이만큼 지나면 "낡았다" 고 적습니다. 권고는 아닙니다.
STALE_DAYS = 365


def bundle_meta(kind: str) -> dict | None:
    p = KIT / BUNDLE[kind] / "meta.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def weekly(kinds: list[str]) -> dict[tuple[str, str], list[dict]]:
    """(타겟, 품목) -> 주별 성적. drift_agent 와 **같은 SQL** 을 씁니다.

    같은 사실을 두 곳에서 다르게 계산하지 않습니다.
    """
    ops = [BUNDLE[k] for k in kinds]
    with db() as c:
        rows = c.execute(SQL, (ops,)).fetchall()
    out: dict[tuple[str, str], list[dict]] = {}
    for wk, kind, item, n, wmape, wa, gain in rows:
        out.setdefault((kind, item), []).append(
            dict(wk=wk, n=int(n), wmape=float(wmape or 0),
                 anchor=float(wa or 0), gain=None if gain is None else float(gain)))
    return out


def check_stale(rep: Report, kinds: list[str]) -> None:
    """학습이 언제 끝났나. **권고가 아니라 기록입니다.**"""
    today = datetime.date.today()
    for k in kinds:
        m = bundle_meta(k)
        if m is None:
            rep.add(Finding(WARN, f"{k} — 번들을 못 찾습니다",
                            f"{KIT / BUNDLE[k]} 에 meta.json 이 없습니다."))
            continue
        te = m.get("train_end")
        if not te:
            continue
        end = datetime.date.fromisoformat(str(te)[:10])
        days = (today - end).days
        nums = [("학습 끝난 날", str(end)),
                ("지난 날수", f"{days}일"),
                ("시드", f"{len(m.get('seeds', []))}개"),
                ("번들 만든 날", str(m.get("created_at", ""))[:10])]
        if days > STALE_DAYS:
            rep.add(Finding(
                WARN, f"{k} — 학습이 {days}일 전에서 멈춰 있습니다",
                "그 뒤 자료를 한 번도 안 배웠습니다.\n"
                "★ 이것만으로 재학습을 권하지 않습니다 — 자료를 더 준다고 좋아지지\n"
                "  않습니다 (학습 시작을 2015 -> 2017 로 줄이니 +5.9% -> +6.8%).\n"
                "  밀림(아래)이 같이 잡힐 때 근거가 됩니다.",
                nums))
        else:
            rep.add(Finding(OK, f"{k} — 학습 시점은 최근입니다", numbers=nums))


def check_drift(rep: Report, kinds: list[str],
                min_rows: int, gap_pp: float, streak: int) -> list[tuple]:
    """밀림을 본다. drift_agent 와 같은 규칙이고, **재학습 관점**으로 다시 적는다.

    돌려주는 것: 재학습 후보 목록 [(kind, item, recent)]
    """
    series = weekly(kinds)
    if not series:
        rep.add(Finding(WARN, "채점된 예측이 없습니다",
                        "score_predictions.py 가 돌아야 오차 이력이 쌓입니다."))
        return []

    hits: list[tuple] = []
    for (kind, item), ws in sorted(series.items()):
        usable = [w for w in ws if w["n"] >= min_rows and w["gain"] is not None]

        #   ★ 판정에서 빼는 계열 (2026-09-11 · drift_agent 의 SKIP_KINDS 그대로).
        #     09-10 에 보고서(drift_agent)에서만 빼고 여기는 안 뺐다. 그래서
        #     중도매가도 재학습 후보로 올라가 **질 수밖에 없는 후보**를 만들
        #     수 있었다. 숫자는 적고 판정만 안 한다 — 조용히 빼지 않는다.
        if kind in SKIP_KINDS:
            nums = [(str(w["wk"]), "모델 %.1f%% · 앵커 %.1f%% (차 %+.1f%%p · %d행)"
                     % (w["wmape"], w["anchor"], w["wmape"] - w["anchor"], w["n"]))
                    for w in usable[-1:]]
            rep.add(Finding(
                OK, f"{kind} {item} — 판정 안 함",
                "중도매가는 열흘 중 엿새가 어제와 값이 같아 앵커가 거의 완벽합니다.\n"
                "밀린 것이 아니라 이길 수 없는 계열이라 재학습 후보로 안 올립니다.", nums))
            continue

        need = BASE_WEEKS + streak
        if len(usable) < need:
            rep.add(Finding(OK, f"{kind} {item} — 아직 판정 못 합니다",
                            f"쓸 수 있는 주가 {len(usable)}개입니다. {need}개는 있어야 합니다.\n"
                            "★ '정상' 이 아니라 '아직 모름' 입니다.",
                            [("한 주 최소 행수", f"{min_rows}행")]))
            continue

        recent = usable[-streak:]
        bad = [w for w in recent if (w["wmape"] - w["anchor"]) > gap_pp]
        nums = [(str(w["wk"]),
                 "모델 %.1f%% · 앵커 %.1f%% (차 %+.1f%%p · %d행)"
                 % (w["wmape"], w["anchor"], w["wmape"] - w["anchor"], w["n"]))
                for w in recent]

        if len(bad) == streak:
            #   ★ 앵커가 유난히 잘 맞았을 뿐인가를 가른다.
            #     중도매가는 열흘 중 엿새가 어제와 같아 조용한 달에 앵커가
            #     0.7% 까지 내려간다. 그때 모델 6.8% 는 나쁜 것이 아니다.
            #     경락가는 매일 움직여서 이 일이 거의 없지만, --kinds 를
            #     풀었을 때를 위해 검사는 둔다.
            worst = max(w["wmape"] for w in recent)
            anchor_hi = max(w["anchor"] for w in recent)
            if anchor_hi < 3.0 and worst < 10.0:
                rep.add(Finding(
                    WARN, f"{kind} {item} — 밀렸지만 앵커가 유난히 잘 맞았습니다",
                    "모델이 나빠진 게 아니라 어제값이 거의 정확했습니다.\n"
                    "★ 재학습 후보로 안 올립니다.",
                    nums + [("최근 앵커 오차 최대", f"{anchor_hi:.1f}%"),
                            ("최근 모델 오차 최대", f"{worst:.1f}%")]))
                continue

            hits.append((kind, item, recent))
            rep.add(Finding(
                BAD, f"{kind} {item} — {streak}주 연속 앵커에 밀렸습니다 · 재학습 후보",
                "모델이 어제값보다 못한 상태가 이어집니다.\n"
                "★ 값이 흔들려서가 아닙니다 — 앵커도 같이 흔들리면 이 차이는 유지됩니다.",
                nums,
                "python agent/retrain_build.py --kind %s 로 후보를 만들어 견주십시오." % kind))
        elif bad:
            rep.add(Finding(
                WARN, f"{kind} {item} — 최근 {len(bad)}주가 앵커보다 나쁩니다",
                f"{streak}주 연속이면 후보로 올립니다. 아직 아닙니다.", nums))
        else:
            rep.add(Finding(OK, f"{kind} {item} — 앵커보다 낫거나 비슷", numbers=nums))
    return hits


def verdict(rep: Report, hits: list[tuple], kinds: list[str]) -> None:
    """마지막 한 줄. **사람이 무엇을 하면 되나**를 적는다."""
    if not hits:
        rep.add(Finding(
            OK, "재학습할 이유가 없습니다",
            "밀린 조합이 없습니다. 학습이 낡았다는 것만으로는 안 겁니다.\n"
            "★ 이 판정은 채점된 주가 쌓여야 뜻이 있습니다. 위의 '아직 판정 못 합니다'\n"
            "  를 같이 보십시오."))
        return

    lines = "\n".join(f"  {k} {i}" for k, i, _ in hits)
    rep.add(Finding(
        BAD, f"재학습 후보 {len(hits)}개",
        "아래 조합이 앵커에 계속 밀립니다.\n" + lines + "\n"
        "★ 자동으로 재학습하지 않습니다. 나쁜 구간을 그대로 배울 위험이 있습니다.\n"
        "  후보를 만들어 **2026 실전 창으로 견준 뒤** 사람이 정합니다.",
        advice="python agent/retrain_build.py --kind %s" % hits[0][0]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", nargs="+", default=DEFAULT_KINDS,
                    choices=["auc", "whsl", "rtl"],
                    help="기본은 auc 하나 — 매입이 읽는 것이 그것뿐입니다")
    ap.add_argument("--min-rows", type=int, default=MIN_ROWS)
    ap.add_argument("--gap-pp", type=float, default=GAP_PP)
    ap.add_argument("--streak", type=int, default=STREAK)
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()

    rep = Report("재학습판정")
    check_stale(rep, a.kinds)
    hits = check_drift(rep, a.kinds, a.min_rows, a.gap_pp, a.streak)
    verdict(rep, hits, a.kinds)

    print(rep.text())
    if a.save:
        print("기록:", rep.save())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
