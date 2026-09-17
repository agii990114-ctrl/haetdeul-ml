# -*- coding: utf-8 -*-
"""현행이 이미 최신이면 **후보를 만들지 않는다.**

## 어떻게 돌리나

    cd C:\\IDE\\workplace\\mainproject_jh_workplace
    set PYTHONIOENCODING=utf-8
    python agent/tests/test_retrain_skip_up_to_date.py

통과하면 종료코드 0, 실패하면 1 이다. 무엇이 어긋났는지 `*** 실패:` 줄로 찍는다.
**DB 도 번들도 안 쓴다** — 가짜 폴더를 임시 자리에 만들어 돌린다. 학습 함수는
바꿔치기(monkeypatch)라 한 번도 안 돈다.

## 무엇을 지키나

후보의 학습 끝은 늘 «견주는 창 하루 전»(2025-12-31)로 **고정**이다. 그런데
2026-09-15 저녁에 소매가 운영 모델이 **바로 그 2025-12-31 까지 학습된 것**으로
교체됐다. 그래서 09-16 부터 매일 **현행과 똑같은 모델**을 새로 학습해
자기 자신과 견줬다 — 세 품목 모두 차이 0.0000, «판정 불가».

    18초 헛학습만 문제가 아니다. **소매가가 진짜 나빠져도 이 점검은
    영원히 «판정 불가» 를 낸다** — 고장을 못 잡는 검사가 된다.

그래서 이 시험이 지키는 것은 넷이다.

    ① 현행 train_end ≥ 후보 end 이면 **학습 함수가 한 번도 안 불린다**
    ② 그때 보고서 제목에 **«건너뜀»** 이 들어간다 (판정은 `정상`이지만
       «문제 없음» 과 헷갈리면 안 된다 — 잰 것이 아니라 **안 잰** 것이다)
    ③ 결과 JSON 이 기존과 같은 모양이고 `skipped` 가 참이다
    ④ 현행이 더 오래됐으면(경락가 2023-12-31) **지금 경로 그대로** —
       후보를 만들고 견준다. 이쪽이 바뀌면 안 된다
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "agent"))

import retrain_build as rb                                 # noqa: E402

#: 후보가 갖게 될 학습 끝. 견주는 창(2026-01-01) 하루 전.
CAND_END = "2025-12-31"


def make_kit(tmp: Path, train_end: dict) -> None:
    """가짜 번들 폴더. `meta.json` 의 `train_end` 만 있으면 된다."""
    for kind, end in train_end.items():
        d = tmp / rb.BUNDLE[kind]
        d.mkdir(parents=True, exist_ok=True)
        (d / "meta.json").write_text(json.dumps({
            "train_start": "2017-01-01", "train_end": end,
            "target_col": f"target_{kind}_prc", "gate_lt": 3,
            "items": ["배추", "양파", "무"], "seeds": [42, 43, 44, 45, 46],
        }, ensure_ascii=False), encoding="utf-8")


def run(kind: str, tmp: Path, out_json: Path) -> tuple[str, list, list]:
    """`retrain_build.main()` 을 한 번 돌린다. 학습·견주기는 가짜로 바꾼다.

    돌려주는 것 = (찍힌 글, 학습 호출 기록, 견주기 호출 기록)
    """
    built: list = []
    judged: list = []

    def fake_build(k, csv, cur_meta, train_end, out):
        built.append((k, str(train_end), Path(out).name))
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "meta.json").write_text(
            json.dumps({"train_end": train_end}), encoding="utf-8")

    def fake_judge(rep, k, csv, cur, cand, eval_from, table=None):
        judged.append((k, Path(cand).name))
        rep.add(rb.Finding(rb.WARN, "배추 — 판정 불가", "가짜 견주기입니다.",
                           [("현행 WMAPE", "0.1000"), ("후보 WMAPE", "0.1000")]))
        if table is not None:
            table.append({"item": "배추", "n": 999, "verdict": "판정 불가"})
        return False

    def fake_dump_csv(dest):
        Path(dest).write_text("가짜 CSV\n", encoding="utf-8")
        return Path(dest)

    old = (rb.KIT, rb.build, rb.judge, rb.dump_csv, list(sys.argv))
    rb.KIT, rb.build, rb.judge, rb.dump_csv = tmp, fake_build, fake_judge, fake_dump_csv
    sys.argv = ["retrain_build.py", "--kind", kind, "--json", str(out_json)]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = rb.main()
    finally:
        rb.KIT, rb.build, rb.judge, rb.dump_csv = old[:4]
        sys.argv = old[4]
    text = buf.getvalue()
    if rc != 0:
        text += f"\n[종료코드 {rc}]"
    return text, built, judged


def main() -> int:
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="retrain_skip_"))
    try:
        make_kit(tmp, {"rtl": CAND_END, "auc": "2023-12-31"})

        # ── ① 현행이 이미 최신 (소매가 · 2025-12-31) ──────────────────
        out_json = tmp / "rtl.json"
        text, built, judged = run("rtl", tmp, out_json)
        print("── 소매가 (현행 학습 끝 2025-12-31) ──")
        print(text.strip())
        res = json.loads(out_json.read_text(encoding="utf-8"))
        print("  JSON:", {k: res[k] for k in ("kind", "candidate", "passed",
                                              "skipped", "verdict")})

        if built:
            print(f"*** 실패: 학습이 불렸습니다 — {built}")
            ok = False
        if judged:
            print(f"*** 실패: 견주기가 불렸습니다 — {judged}")
            ok = False
        title = (res.get("findings") or [{}])[0].get("title", "")
        if "건너뜀" not in title:
            print(f"*** 실패: 보고서 제목에 «건너뜀» 이 없습니다 — {title!r}")
            ok = False
        if "건너뜀" not in text:
            print("*** 실패: 찍힌 글에 «건너뜀» 이 없습니다")
            ok = False
        if res.get("skipped") is not True:
            print(f"*** 실패: JSON 의 skipped 가 {res.get('skipped')!r}")
            ok = False
        if res.get("candidate") != "":
            print(f"*** 실패: 후보 이름이 남았습니다 — {res.get('candidate')!r}")
            ok = False
        if res.get("passed") is not False:
            print(f"*** 실패: passed 가 {res.get('passed')!r} — 통과가 아니라 안 잰 것입니다")
            ok = False
        if res.get("verdict") != "정상":
            print(f"*** 실패: 판정이 {res.get('verdict')!r} — «정상» 이어야 합니다")
            ok = False
        #   모양이 안 바뀌어야 화면·채팅이 안 깨진다
        for key in ("kind", "candidate", "eval_from", "passed", "verdict",
                    "at", "items", "findings"):
            if key not in res:
                print(f"*** 실패: JSON 에 {key} 칸이 없습니다")
                ok = False
        got = {k: v for f in res["findings"] for k, v in (f.get("numbers") or [])}
        for key, want in (("현행 학습 끝", CAND_END), ("후보가 됐을 학습 끝", CAND_END)):
            if got.get(key) != want:
                print(f"*** 실패: 수치 «{key}» 가 {got.get(key)!r} (기대 {want})")
                ok = False
        made = [p.name for p in tmp.glob("ops_rtl_cand_*")]
        if made:
            print(f"*** 실패: 후보 폴더가 만들어졌습니다 — {made}")
            ok = False

        # ── ② 현행이 더 오래됐다 (경락가 · 2023-12-31) ────────────────
        out_json2 = tmp / "auc.json"
        text2, built2, judged2 = run("auc", tmp, out_json2)
        res2 = json.loads(out_json2.read_text(encoding="utf-8"))
        print("\n── 경락가 (현행 학습 끝 2023-12-31) ──")
        print("  학습 호출:", built2)
        print("  견주기 호출:", judged2)
        print("  JSON:", {k: res2.get(k) for k in ("kind", "candidate", "passed",
                                                   "skipped", "verdict")})

        if len(built2) != 1:
            print(f"*** 실패: 학습이 1번이어야 하는데 {len(built2)}번 — {built2}")
            ok = False
        elif built2[0][1] != CAND_END:
            print(f"*** 실패: 후보 학습 끝이 {built2[0][1]} (기대 {CAND_END})")
            ok = False
        if len(judged2) != 1:
            print(f"*** 실패: 견주기가 1번이어야 하는데 {len(judged2)}번")
            ok = False
        if res2.get("skipped") is not False:
            print(f"*** 실패: 경락가는 건너뛰면 안 됩니다 — skipped {res2.get('skipped')!r}")
            ok = False
        if "건너뜀" in text2:
            print("*** 실패: 경락가 글에 «건너뜀» 이 들어갔습니다")
            ok = False
        if not res2.get("candidate", "").startswith("ops_auc_cand_"):
            print(f"*** 실패: 후보 이름이 {res2.get('candidate')!r}")
            ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n통과" if ok else "\n실패")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
