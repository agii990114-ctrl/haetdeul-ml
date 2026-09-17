# -*- coding: utf-8 -*-
"""지나간 모델 교체를 `model_cutover` 에 밀어 넣는다.  (2026-09-16)

## 왜 필요한가

이력을 남기는 코드는 오늘 붙였다. 그 전에 일어난 교체는 **백업 폴더
이름 말고는 아무 흔적이 없다.** 2026-09-15 저녁에 소매가 모델이
바뀐 것이 그렇다 — `ops_rtl_교체전_20260915` 폴더 하나가 전부다.

여기서 그 폴더들을 훑어 한 행씩 만든다.

## 교체 «시각» 을 어떻게 잡나 — 여기가 이 파일의 어려운 곳

윈도우에서 폴더의 **만든 시각**은 `os.stat(폴더).st_ctime` 이다.
`st_mtime`(고친 시각)은 번들 **내용**의 시각이라 교체 시각이 아니다.

    ops_rtl_교체전_20260915   ctime 2026-09-15 19:57:24   <- 교체한 때
                              mtime 2026-09-08 19:07:44   <- 번들을 만든 때

**그런데 늘 맞지는 않는다.** 백업을 «복사» 로 만들면 ctime 이 복사한
때(=교체 때)지만, «이름 바꾸기» 로 만들면 NTFS 가 **만든 시각을
그대로 물려준다.** 그러면 ctime 은 옛 번들이 생긴 때가 된다.

    ops_whsl_교체전_20260909  ctime 2026-09-03 10:42:38   <- 09-09 가 아니다

그래서 규칙을 이렇게 둔다.

    ① 이름에 박힌 날짜와 ctime 의 날짜가 **같으면**  ctime 을 쓴다
    ② 기록된 시각이 있으면(2026-09-03 분위수 교체)   그 시각을 쓴다
    ③ 둘 다 아니면  그 날 00:00:00 으로 두고 **note 에 «추정» 을 적는다**

**모르는 것을 그럴듯하게 채우지 않는다.** 00:00 은 «그날인 건 맞고
시각은 모른다» 는 뜻이고, note 에 실제로 본 ctime·mtime 을 적어 둔다.

## 두 번 돌려도 안전하다

표에 `UNIQUE (kind, swapped_at)` 이 있고 `log_cutover` 가
`ON CONFLICT DO NOTHING` 이다. 같은 교체가 두 벌이 되지 않는다.

## 쓰는 법

    python ops/cutover_backfill.py            # 무엇을 넣을지 보기만
    python ops/cutover_backfill.py --commit   # 실제로 넣는다
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")   # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "ML" / "20260824" / "ml_train_kit_2"
sys.path.insert(0, str(ROOT / "agent"))

from core import KIND_UP, bundle_info, log_cutover           # noqa: E402

LIVE = {"auc": "ops_auc", "whsl": "ops_whsl", "rtl": "ops_rtl"}

#:  백업 폴더 이름 두 가지.
#:    _교체전_  agent/retrain_build.py 의 apply() 가 만든다
#:    _pre_     ML/.../cutover_quantile.py 가 만든다. 한글을 못 쓰는 이유는
#:              LightGBM 이 C++ 라 한글 경로를 못 열기 때문이다 (그 파일 머리말)
PAT = re.compile(r"^ops_(auc|whsl|rtl)_(교체전|pre)_(\d{8})$")

#:  문서에 기록이 남은 교체 시각. **폴더에서 못 읽는 것만 여기 둔다.**
#:  2026-09-03 10:36 분위수 교체 — CLAUDE.md §5.11 에 못박혀 있다.
KNOWN = {
    ("auc", "20260903"): (datetime.datetime(2026, 9, 3, 10, 36, 0),
                          "분위수 밴드 교체 (cutover_quantile.py --commit). "
                          "시각은 CLAUDE.md §5.11 에 기록된 10:36"),
    ("whsl", "20260903"): (datetime.datetime(2026, 9, 3, 10, 36, 0),
                           "분위수 밴드 교체 (cutover_quantile.py --commit). "
                           "시각은 CLAUDE.md §5.11 에 기록된 10:36"),
}


def count() -> int:
    """표에 몇 행이 있나. 못 세면 -1 — **0 이라고 말하지 않는다.**"""
    try:
        from core import db                                  # noqa: PLC0415
        with db() as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM model_cutover")
            return int(cur.fetchone()[0])
    except Exception:                                        # noqa: BLE001
        return -1


def fix_time_known(rows: list) -> None:
    """이미 들어 있는 행의 `time_known` 만 맞춘다.

    ★ **왜 따로 필요한가.** `log_cutover` 는 `ON CONFLICT DO NOTHING` 이다.
      이미 있는 교체는 **한 칸도 안 고친다** — 그게 «두 번 돌려도 안전하다»
      의 뜻이다. 그런데 `time_known` 칸은 그 행들이 들어간 **뒤에** 생겼다.
      그래서 이 한 칸만 따로 맞춰 준다.

    ★ 고치는 것은 `time_known` **하나뿐이다.** `swapped_at` · `note` ·
      `actor` 는 안 건드린다. 나중에 사람이 손으로 고쳐 둔 값을
      백필이 되돌려 놓으면 안 된다.
    """
    try:
        from core import KIND_UP as _KU, db                   # noqa: PLC0415
        with db() as c:
            with c.cursor() as cur:
                for r in rows:
                    cur.execute(
                        "UPDATE model_cutover SET time_known = %s"
                        " WHERE kind = %s AND swapped_at = %s"
                        "   AND time_known IS DISTINCT FROM %s",
                        (r["time_known"], _KU[r["kind"]], r["at"],
                         r["time_known"]))
                    if cur.rowcount:
                        print(f"  time_known 고침  {_KU[r['kind']]} "
                              f"{r['at']:%Y-%m-%d %H:%M:%S} -> {r['time_known']}")
            c.commit()
    except Exception as e:                                    # noqa: BLE001
        print(f"  ★ time_known 을 못 맞췄습니다: {type(e).__name__}: {e}")


def when(t: float) -> str:
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def plan() -> list[dict]:
    """백업 폴더를 훑어 넣을 행을 만든다. **DB 는 안 건드린다.**"""
    found: dict[str, list] = {"auc": [], "whsl": [], "rtl": []}
    for p in sorted(KIT.iterdir()):
        if not p.is_dir():
            continue
        m = PAT.match(p.name)
        if not m:
            continue
        found[m.group(1)].append((m.group(3), m.group(2), p))

    out: list[dict] = []
    for kind, items in found.items():
        items.sort()                      # 날짜순 — 옛것부터
        for i, (ymd, style, path) in enumerate(items):
            st = os.stat(path)
            day = datetime.date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
            ct = datetime.datetime.fromtimestamp(st.st_ctime)
            mt = datetime.datetime.fromtimestamp(st.st_mtime)

            #   ── 새로 꽂힌 번들이 어느 것이었나 ──────────────────
            #   ★ 분위수 교체(_pre_)는 무엇을 올렸는지 코드에 적혀 있다 —
            #     cutover_quantile.py 의 PAIRS 가 ops_{kind}_q 를 올린다.
            #     그 밖에는 **다음 백업이 곧 그때 꽂힌 것**이다.
            #     다음 백업이 없으면 지금 꽂혀 있는 것이다.
            if style == "pre" and (KIT / f"ops_{kind}_q").is_dir():
                new_dir = KIT / f"ops_{kind}_q"
                chain = "cutover_quantile.py PAIRS"
            elif i + 1 < len(items):
                new_dir = items[i + 1][2]
                chain = "다음 백업 폴더"
            else:
                new_dir = KIT / LIVE[kind]
                chain = "지금 꽂혀 있는 번들"

            #   ── 교체 시각 ────────────────────────────────────
            note_bits = [f"백필 · 새 번들 출처={chain}",
                         f"폴더 st_ctime={when(st.st_ctime)}",
                         f"st_mtime={when(st.st_mtime)}"]
            known = KNOWN.get((kind, ymd))
            if known:
                at, why = known[0], known[1]
                note_bits.insert(0, why)
                basis = "문서 기록"
                time_known = True
            elif ct.date() == day:
                at = ct.replace(microsecond=0)
                basis = "폴더 만든 시각(st_ctime)"
                time_known = True
                note_bits.insert(0, "교체 시각 = 백업 폴더를 만든 시각")
            else:
                at = datetime.datetime.combine(day, datetime.time(0, 0, 0))
                basis = "★ 추정 (날짜만)"
                #   ★ 00:00 은 «자정에 바꿨다» 가 아니라 «시각을 모른다» 다.
                #     그 뜻을 글(note)에만 담으면 화면이 못 읽는다. 그래서
                #     `time_known` 칸으로도 같이 말한다.
                time_known = False
                note_bits.insert(
                    0, "★ 추정 — 폴더 이름의 날짜는 확실하나 시각은 모름. "
                       "st_ctime 이 이름의 날짜와 달라 쓸 수 없음 "
                       "(이름 바꾸기로 만든 백업은 옛 번들의 만든 시각을 물려받음)")

            out.append({"kind": kind, "model_ver": LIVE[kind],
                        "old_dir": path, "new_dir": new_dir,
                        "at": at, "basis": basis, "time_known": time_known,
                        "ctime": ct, "mtime": mt,
                        "note": " · ".join(note_bits)})
    out.sort(key=lambda r: (r["at"], r["kind"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="지나간 모델 교체를 표에 밀어 넣는다")
    ap.add_argument("--commit", action="store_true", help="실제로 넣는다")
    a = ap.parse_args()

    rows = plan()
    if not rows:
        print("백업 폴더를 못 찾았습니다:", KIT)
        return 1

    print("=" * 78)
    print("[지나간 모델 교체 — 백업 폴더에서 읽은 것]")
    print("=" * 78)
    print(f"{'종류':<6}{'백업 폴더':<28}{'ctime':<21}{'mtime':<21}")
    print("-" * 78)
    for r in rows:
        print(f"{r['kind']:<6}{r['old_dir'].name:<28}"
              f"{r['ctime']:%Y-%m-%d %H:%M:%S}  {r['mtime']:%Y-%m-%d %H:%M:%S}")
    print()
    for r in rows:
        o = bundle_info(r["old_dir"])
        n = bundle_info(r["new_dir"])
        print(f"  {KIND_UP[r['kind']]:<5} {r['at']:%Y-%m-%d %H:%M:%S}  ({r['basis']})"
              f"   time_known={r['time_known']}")
        print(f"        옛 {o[0]}  학습끝 {o[1]}  만든날 {o[2]}")
        print(f"        새 {n[0]}  학습끝 {n[1]}  만든날 {n[2]}")
    print()

    if not a.commit:
        print(f"--commit 이 없어 아무것도 안 넣었습니다. ({len(rows)}건 예정)")
        return 0

    #   ★ 넣기 전후로 행수를 센다. `log_cutover` 는 «보냈다» 만 알려주고,
    #     이미 있어서 건너뛴 것과 새로 들어간 것을 구분해 주지 않는다.
    #     두 번째로 돌릴 때 «5건 넣음» 이라고 찍히면 사람이 두 벌이 된 줄
    #     안다. **센 것만 말한다.**
    before = count()
    sent = 0
    for r in rows:
        got = log_cutover(r["kind"], r["model_ver"], r["old_dir"], r["new_dir"],
                          swapped_at=r["at"], actor="추정(백업 폴더)",
                          note=r["note"], time_known=r["time_known"])
        print(f"  {'보냄' if got else '★ 실패'}  {KIND_UP[r['kind']]} "
              f"{r['at']:%Y-%m-%d %H:%M:%S}  {r['old_dir'].name}"
              f"{'' if r['time_known'] else '   ← 시각 모름'}")
        sent += bool(got)
    fix_time_known(rows)
    after = count()
    print(f"\n보낸 것 {sent}/{len(rows)}건 · "
          f"표의 행수 {before} -> {after} (새로 들어간 것 {after - before}건)")
    print("  같은 (종류·시각)이 이미 있으면 조용히 건너뜁니다 — 두 벌이 안 됩니다.")
    return 0 if sent == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
