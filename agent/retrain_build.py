#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""재학습 후보를 만들고 **견준다**. 교체는 사람이 한다.

    스프린트 4 의 ③ 입니다 — *"새 모델이 검증을 통과하지 못하면 교체되지 않는다."*

    ─────────────────────────────────────────────────────────────────
    ★ 어떻게 공정하게 견주나 — 이게 이 파일의 전부입니다

        현행    학습 2017-01-01 ~ 2023-12-31
        후보    학습 2017-01-01 ~ (견주는 창 하루 전)
        견줌    2026-01-01 ~ 오늘        ← **둘 다 안 본 구간**

        후보를 오늘까지 학습시키면 2026 으로 못 잽니다. 자기가 본 걸 맞히는
        것이라 무조건 이깁니다. 그래서 **후보의 학습을 견주는 창 앞에서
        끊습니다.** 그러면 현행(2023까지)과 후보(2025까지) 둘 다 2026 을
        처음 봅니다.

        ⚠️ 봉인(2024~2025)은 안 엽니다. 2026 은 이미 여러 번 잰 창입니다.

    ★ 판정 규칙 — 우리가 여러 번 데인 것을 그대로 씁니다

        ① 품목별로 본다        통합값은 비싼 품목이 지배한다 (마늘이 분모 66%)
        ② 편차×2 를 넘어야 한다  시드마다 흔들리는 폭보다 커야 개선이다
        ③ 한 품목이 좋아지고 다른 품목이 나빠지면 **채택 안 한다**
           경락 양파 분리가 3폴드를 통과하고도 운영에서 배추 −5.70% 였다

    ★ 안 하는 것

        자동 교체를 안 합니다. `--apply` 를 사람이 직접 쳐야 바뀝니다.
        그리고 바꾸기 전에 현행을 통째로 백업합니다.

    쓰는 법
        python agent/retrain_build.py --judge-only          # 있는 후보만 견줌
        python agent/retrain_build.py --kind auc            # 후보를 만들고 견줌
        python agent/retrain_build.py --kind auc --cand ops_auc_s20 --judge-only
        python agent/retrain_build.py --kind auc --apply    # 교체 (확인 후)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import io
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import Finding, Report, OK, WARN, BAD, log_cutover  # noqa: E402

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
sys.path.insert(0, str(KIT))

BUNDLE = {"auc": "ops_auc", "whsl": "ops_whsl", "rtl": "ops_rtl"}
LABEL = {"auc": "경락가", "whsl": "중도매가", "rtl": "소매가"}

#: 견주는 창의 시작. 2026 은 봉인이 아니고 이미 여러 번 잰 구간입니다.
EVAL_FROM = "2026-01-01"


# ─────────────────────────────────────────────────────────────────────
#   번들로 예측하기 — predict.py 의 함수를 그대로 빌린다
#
#   ★ 여기서 앵커 계산이나 역변환을 다시 짜면 안 됩니다.
#     운영이 쓰는 코드와 한 글자라도 다르면 **운영이 아닌 것을 재게** 됩니다.
#     실험 도구가 마늘을 24% 섞어 학습하던 것을 못 보고 판정을 낸 적이 있습니다.
# ─────────────────────────────────────────────────────────────────────
def predict_with(bundle_dir: Path, df: pd.DataFrame):
    """번들 하나로 예측한다. 시드별 예측도 같이 돌려준다 (편차용)."""
    from predict import load_bundle, prepare          # noqa: E402  (KIT 경로 필요)

    meta, models, _q = load_bundle(str(bundle_dir))
    anchor_col = meta["anchor_col"]
    alpha = float(meta.get("anchor_alpha", 1.0))
    d = df.copy()

    if alpha < 1.0:
        avg7 = anchor_col.replace("_lag1", "_avg7")
        if avg7 not in d.columns:
            raise SystemExit(f"{bundle_dir.name}: 수축 앵커(α={alpha})인데 {avg7} 가 없습니다.")
        mix = (alpha * d[anchor_col] + (1 - alpha) * d[avg7]).fillna(d[anchor_col])
        d = d.assign(_anchor_mix=mix)
        anchor_col = "_anchor_mix"
    elif "_anchor_mix" in (meta.get("features") or []):
        d = d.assign(_anchor_mix=d[anchor_col])

    X = prepare(d, meta)
    anchor = d[anchor_col].to_numpy(float)
    per_seed = [anchor * np.exp(m.predict(X)) for m in models]   # ★ 역변환
    return meta, np.mean(per_seed, axis=0), per_seed, anchor


def wmape(actual, pred) -> float:
    a = np.asarray(actual, float); p = np.asarray(pred, float)
    tot = np.abs(a).sum()
    return float(np.abs(a - p).sum() / tot) if tot else float("nan")


def load_frame(csv: Path | None, eval_from: str, items: list[str]) -> pd.DataFrame:
    """견줄 자료를 가져온다. **기본은 DB** — 배치가 CSV 를 안 거치므로.

    ★ 학습표(crop_price_train)를 그대로 읽습니다. 거기 정답(target_*)이
      같이 있어 별도 채점이 필요 없습니다.
    """
    if csv and Path(csv).exists():
        df = pd.read_csv(csv)
        df["base_dt"] = pd.to_datetime(df["base_dt"])
        return df

    from core import db                                   # noqa: E402
    q = ("SELECT * FROM crop_price_train "
         "WHERE base_dt >= %s AND item_nm = ANY(%s) ORDER BY base_dt, item_nm, lead_biz_d")
    with db() as c:
        cu = c.execute(q, (eval_from, items))
        rows, cols = cu.fetchall(), [d[0] for d in cu.description]
    df = pd.DataFrame(rows, columns=cols)
    df["base_dt"] = pd.to_datetime(df["base_dt"])
    #   NUMERIC 은 Decimal 로 옵니다. 그대로 두면 LightGBM 이 못 씁니다.
    from decimal import Decimal
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, Decimal)).any():
            df[col] = df[col].astype(float)
    return df


def dump_csv(dest: Path) -> Path:
    """학습표를 통째로 CSV 로 뽑는다. train.py 가 CSV 만 받기 때문이다.

    ★ 배치는 CSV 를 안 거치는데 train.py 는 CSV 를 받습니다. 그 사이를
      여기서 메웁니다. **DB 를 정본으로 두고 CSV 는 매번 새로 뽑습니다** —
      낡은 CSV 가 굴러다니면 어느 것으로 학습했는지 모르게 됩니다.
    """
    from core import db                                   # noqa: E402
    import csv as _csv
    with db() as c:
        cu = c.execute("SELECT * FROM crop_price_train ORDER BY id")
        cols = [d[0] for d in cu.description]
        with io.open(dest, "w", encoding="utf-8", newline="") as f:
            w = _csv.writer(f)
            w.writerow(cols)
            n = 0
            while True:
                chunk = cu.fetchmany(20000)
                if not chunk:
                    break
                w.writerows(chunk)
                n += len(chunk)
    print(f"  학습표를 뽑았습니다: {dest.name} · {n:,}행 · {len(cols)}열")
    return dest


# ─────────────────────────────────────────────────────────────────────
#   후보를 만들기 **전에** — 만들어 봐야 같은 것이면 만들지 않는다
#
#   ★ 2026-09-16. 후보의 학습 끝은 «견주는 창 하루 전» 로 **고정**입니다
#     (`EVAL_FROM` 이 2026-01-01 이니 늘 2025-12-31). 그런데 09-15 저녁에
#     소매가 운영 모델이 **바로 그 2025-12-31 까지 학습된 것**으로 교체됐습니다.
#
#     그러면 매일 **현행과 똑같은 모델**을 새로 학습해 자기 자신과 견줍니다.
#     실제로 09-16 소매가 검증이 세 품목 모두 WMAPE 가 소수점까지 같아
#     «판정 불가» 가 나왔습니다. 그건 모델이 이상해서가 아니라 **견줄 것이
#     없어서**였는데, 그 말이 어디에도 안 적혀 있었습니다.
#
#     ★ 그냥 낭비가 아닙니다. 소매가가 진짜 나빠져도 이 점검은 영원히
#       «판정 불가» 를 냅니다 — **고장을 못 잡는 검사**가 됩니다.
#
#     그래서 **만들기 전에** 현행 `meta.json` 의 `train_end` 를 보고,
#     이미 그 날짜까지 배웠으면 건너뜁니다. 경락가(현행 2023-12-31)는
#     지금처럼 후보를 만들어 견줍니다 — 이 검사에 안 걸립니다.
# ─────────────────────────────────────────────────────────────────────
def cand_train_end(eval_from: str) -> str:
    """후보의 학습 끝. 견주는 창 하루 전이다."""
    return (datetime.date.fromisoformat(eval_from)
            - datetime.timedelta(days=1)).isoformat()


def up_to_date(cur_meta: dict, end: str) -> str | None:
    """현행이 이미 `end` 까지(혹은 그보다 더) 배웠나. 그렇다면 그 날짜를 준다.

    ★ **못 읽으면 None 입니다** — 즉 «지금까지 하던 대로 후보를 만든다».
      읽을 수 없는 것을 «최신이겠지» 로 넘기면 점검이 조용히 멈춥니다.
      건너뛰는 쪽이 아니라 **하던 쪽**이 안전한 기본값입니다.
    """
    raw = cur_meta.get("train_end")
    if not raw:
        return None
    try:
        cur_end = datetime.date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return str(raw) if cur_end >= datetime.date.fromisoformat(end) else None


def skip_report(kind: str, cur_end: str, cand_end: str, eval_from: str) -> Report:
    """«건너뜀» 보고서. **«판정 불가» 가 아니라 «건너뜀» 이라고 적는다.**

    ★ 제목에 **«건너뜀»** 이 들어갑니다. 판정은 `정상`(OK)이지만, 그것만
      보면 사람이 «문제 없음» 으로 읽습니다. 둘은 다릅니다 —
      **잰 것이 아니라 안 잰 것**입니다.
    """
    rep = Report("재학습검증", kind=kind)
    rep.add(Finding(
        OK,
        #   ★ 앞에 **«건너뜀»** 을 붙입니다. 판정은 `정상`이라 그것만 보면
        #     사람이 «문제 없음» 으로 읽습니다. 한 낱말로 갈라 둡니다.
        f"[건너뜀] {LABEL.get(kind, kind)} — 현행이 이미 {cur_end} 까지 학습했습니다 · "
        "견줄 새 후보가 없어 재학습 점검을 건너뜁니다",
        "후보는 늘 «견주는 창 하루 전»(%s)까지 학습합니다. 현행이 이미 거기까지\n"
        "배웠으므로, 만들어 봐야 **현행과 똑같은 모델**입니다.\n"
        "★ 그래서 이 보고서는 «괜찮다» 가 아니라 «안 쟀다» 입니다.\n"
        "  새 후보가 생기려면 견주는 창(%s)을 뒤로 옮기거나, 현행보다 더\n"
        "  최근까지 배운 후보를 따로 만들어 --cand 로 주어야 합니다." % (cand_end, eval_from),
        [("현행 학습 끝", cur_end),
         ("후보가 됐을 학습 끝", cand_end),
         ("견주는 창", f"{eval_from} ~"),
         ("한 일", "후보를 만들지 않았습니다 (학습 안 함)")]))
    return rep


def result_json(dest: Path, kind: str, candidate: str, eval_from: str,
                passed: bool, rep: Report, items: list, skipped: bool = False) -> None:
    """화면·그래프가 읽는 결과 파일. **건너뜀도 같은 모양으로 남긴다.**

    ★ 모양을 바꾸면 화면(3100)과 채팅이 깨집니다. `skipped` 한 칸만 더합니다 —
      읽는 쪽이 모르는 칸은 그냥 무시합니다.
    """
    from dataclasses import asdict                           # noqa: PLC0415
    dest.write_text(json.dumps({
        "kind": kind,
        "candidate": candidate,
        "eval_from": eval_from,
        "passed": passed,
        #   ★ «건너뛰었나». 없으면 거짓으로 읽으면 된다.
        "skipped": skipped,
        "verdict": rep.worst,
        "at": rep.started.strftime("%Y-%m-%d %H:%M:%S"),
        #   ★ 화면이 표로 그리는 자리. 글(findings)과 따로 둡니다 —
        #     문장을 파싱해 숫자를 뽑으면 문장을 고칠 때마다 화면이 깨집니다.
        "items": items,
        "findings": [asdict(f) for f in rep.findings],
    }, ensure_ascii=False, indent=1), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
#   후보 만들기
# ─────────────────────────────────────────────────────────────────────
def build(kind: str, csv: Path, cur_meta: dict, train_end: str, out: Path) -> None:
    """현행과 **똑같은 조리법**으로, 학습 끝 날짜만 바꿔 만든다."""
    cmd = [sys.executable, "train.py", str(csv),
           "--target", kind,
           "--train-start", cur_meta.get("train_start", "2017-01-01"),
           "--train-end", train_end,
           "--gate-lt", str(cur_meta.get("gate_lt", 3)),
           "--anchor-alpha", str(cur_meta.get("anchor_alpha", 1.0)),
           "--fixed-iter", str(cur_meta.get("fixed_iter") or 76),
           "--seeds", *[str(s) for s in cur_meta.get("seeds", [42, 43, 44, 45, 46])],
           "--items", *cur_meta.get("items", ["배추", "양파", "무"]),
           "--save-model", str(out)]

    #   분위수 번들이면 그것도 같이 만든다. 안 그러면 밴드가 사라진다.
    qq = cur_meta.get("quantile_q")
    if cur_meta.get("quantile_models"):
        cmd.append("--quantile")
        if qq:
            cmd += ["--quantile-q", ",".join(f"{k}={v}" for k, v in qq.items())]
        if cur_meta.get("quantile_rounds"):
            cmd += ["--quantile-rounds", str(cur_meta["quantile_rounds"])]

    print("  학습:", " ".join(cmd[1:6]), "...")
    #   ★ train.py 도 같은 이유로 UTF-8 을 받아야 한다 (윈도우 cp949).
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run(cmd, cwd=KIT, env=env)
    if r.returncode != 0:
        raise SystemExit("학습이 실패했습니다. 위 출력을 보세요.")


# ─────────────────────────────────────────────────────────────────────
#   견주기
# ─────────────────────────────────────────────────────────────────────
def judge(rep: Report, kind: str, csv: Path, cur: Path, cand: Path,
          eval_from: str, table: list | None = None) -> bool:
    """현행 vs 후보. 돌려주는 값 = 채택 권고 여부.

    `table` 을 주면 **품목별 수치를 거기 담습니다** — 화면이 표로 그립니다.
    """
    cur_meta = json.loads((cur / "meta.json").read_text(encoding="utf-8"))
    target = cur_meta["target_col"]
    gate = int(cur_meta.get("gate_lt", 3))
    items = cur_meta.get("items", ["배추", "양파", "무"])

    df = load_frame(csv, eval_from, items)
    m = (df["base_dt"] >= eval_from) & df["item_nm"].isin(items) \
        & (df["lead_biz_d"] >= gate) & df[target].notna()
    ev = df[m].copy()

    if table is None:
        table = []

    if ev.empty:
        rep.add(Finding(BAD, "견줄 행이 없습니다",
                        f"{eval_from} 이후 · {items} · LT>={gate} · 정답 있는 행이 0입니다."))
        return False

    rep.add(Finding(OK, "견주는 창",
                    "둘 다 이 구간을 학습에 안 썼습니다.",
                    [("구간", f"{eval_from} ~ {ev['base_dt'].max().date()}"),
                     ("기준일", f"{ev['base_dt'].nunique()}개"),
                     ("행수", f"{len(ev):,}행 (LT>={gate})"),
                     ("현행 학습 끝", str(cur_meta.get("train_end"))),
                     ("후보 학습 끝", str(json.loads(
                         (cand / "meta.json").read_text(encoding="utf-8")
                     ).get("train_end")))]))

    out = {}
    for tag, d in (("현행", cur), ("후보", cand)):
        _meta, pred, per_seed, anchor = predict_with(d, ev)
        out[tag] = dict(pred=pred, per_seed=per_seed, anchor=anchor)

    actual = ev[target].to_numpy(float)
    anchor = out["현행"]["anchor"]

    #   ── 품목별 ──────────────────────────────────────────────────
    #
    #   ★ 글(Finding)과 **따로** 표를 모읍니다. 지금까지는 사람이 읽는
    #     문장만 남기고 수치를 버려서, 화면이 «판정 배추 — 후보가 낫습니다»
    #     한 줄만 보였습니다. **바꿀지 말지는 숫자를 나란히 놓고 정하는
    #     일**이라 표가 있어야 합니다.
    rows = table
    verdicts = []
    for item in items:
        sel = (ev["item_nm"] == item).to_numpy()
        if sel.sum() < 100:
            rep.add(Finding(WARN, f"{item} — 표본이 적어 판정 안 합니다",
                            f"{int(sel.sum())}행뿐입니다.",
                            [("필요", "100행")]))
            rows.append({"item": item, "n": int(sel.sum()), "verdict": "표본 부족",
                         "anchor": None, "cur": None, "cand": None,
                         "diff": None, "need": None})
            verdicts.append(None)
            continue

        a = actual[sel]
        w_cur = wmape(a, out["현행"]["pred"][sel])
        w_cand = wmape(a, out["후보"]["pred"][sel])
        w_anc = wmape(a, anchor[sel])

        #   시드마다 얼마나 흔들리나 — 이 폭의 2배를 넘어야 개선이다
        sd_cur = float(np.std([wmape(a, p[sel]) for p in out["현행"]["per_seed"]]))
        sd_cand = float(np.std([wmape(a, p[sel]) for p in out["후보"]["per_seed"]]))
        need = 2 * max(sd_cur, sd_cand)
        diff = w_cur - w_cand                     # 양수면 후보가 낫다

        nums = [("행수", f"{int(sel.sum()):,}행"),
                ("현행 WMAPE", f"{w_cur:.4f}"),
                ("후보 WMAPE", f"{w_cand:.4f}"),
                ("앵커 WMAPE", f"{w_anc:.4f}"),
                ("차이 (현행−후보)", f"{diff:+.4f}"),
                ("시드 편차×2", f"{need:.4f}")]

        if diff > need:
            verdict = "후보가 낫다"
            verdicts.append(True)
            rep.add(Finding(OK, f"{item} — 후보가 낫습니다", "편차×2 를 넘습니다.", nums))
        elif -diff > need:
            verdict = "후보가 나쁘다"
            verdicts.append(False)
            rep.add(Finding(BAD, f"{item} — 후보가 **나쁩니다**", "편차×2 를 넘어 나쁩니다.", nums))
        else:
            verdict = "판정 불가"
            verdicts.append(None)
            rep.add(Finding(WARN, f"{item} — 판정 불가",
                            "차이가 시드 흔들림 안입니다. **'같다' 가 아니라 '모른다' 입니다.**",
                            nums))

        rows.append({"item": item, "n": int(sel.sum()), "verdict": verdict,
                     "anchor": round(w_anc, 4), "cur": round(w_cur, 4),
                     "cand": round(w_cand, 4), "diff": round(diff, 4),
                     "need": round(need, 4)})

    #   ── 최종 ────────────────────────────────────────────────────
    better = sum(1 for v in verdicts if v is True)
    worse = sum(1 for v in verdicts if v is False)

    if worse:
        rep.add(Finding(
            BAD, "채택하지 않습니다 — 나빠지는 품목이 있습니다",
            f"좋아진 품목 {better}개 · 나빠진 품목 {worse}개.\n"
            "★ 한쪽이 좋아지고 다른 쪽이 나빠지면 안 바꿉니다.\n"
            "  경락 양파를 따로 뗀 안이 3폴드를 통과하고도 운영에서 배추 −5.70% 였습니다."))
        return False
    if better == 0:
        rep.add(Finding(
            WARN, "채택하지 않습니다 — 나아진 것을 증명 못 했습니다",
            "나빠진 품목은 없지만 좋아진 것도 편차×2 를 못 넘었습니다.\n"
            "★ '판정 불가' 는 '기여 없음' 이 아닙니다. 증명을 못 한 것입니다.\n"
            "  바꿀 이유가 없으니 안 바꿉니다."))
        return False

    rep.add(Finding(
        OK, f"채택할 만합니다 — {better}개 품목이 좋아지고 나빠진 품목이 없습니다",
        "★ 그래도 자동으로 안 바꿉니다. 사람이 정합니다.",
        advice="python agent/retrain_build.py --kind %s --cand %s --apply" % (kind, cand.name)))
    return True


# ─────────────────────────────────────────────────────────────────────
#   교체 — 사람이 --apply 를 쳐야 한다
# ─────────────────────────────────────────────────────────────────────
def apply(kind: str, cur: Path, cand: Path, actor: str = "사람") -> None:
    """교체한다. 지금 것을 통째로 백업하고 **이름은 그대로 둔다.**

    ★ 교체 사실을 `model_cutover` 에 한 행 남긴다 (2026-09-16).
      **이름이 안 바뀌기 때문에** 남기지 않으면 나중에 «언제 무엇으로
      바뀌었나» 를 답할 길이 없다. 실제로 09-15 소매가 교체가 그랬다 —
      백업 폴더 이름 하나만 남았다.

      `log_cutover` 는 실패해도 예외를 안 올린다. 이력을 «알리다가»
      교체를 망치면 본말전도다.
    """
    stamp = datetime.date.today().strftime("%Y%m%d")
    bak = cur.parent / f"{cur.name}_교체전_{stamp}"
    if bak.exists():
        shutil.rmtree(bak)
    shutil.copytree(cur, bak)
    shutil.rmtree(cur)
    shutil.copytree(cand, cur)
    log_cutover(kind, cur.name, bak, cand, actor=actor,
                note=f"{cand.name} -> {cur.name} (retrain_build.apply)")
    print(f"\n교체했습니다.  {cand.name} -> {cur.name}")
    print(f"되돌리려면:  rm -rf {cur} && cp -r {bak} {cur}")
    print("★ 번들 이름은 그대로입니다 — 매입 파트 필터가 정확히 일치로 걸어서 바꾸면 0건이 됩니다.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="auc", choices=["auc", "whsl", "rtl"])
    ap.add_argument("--csv", help="학습 CSV. 안 주면 번들 meta 의 source_csv")
    ap.add_argument("--cand", help="이미 있는 후보 번들 이름 (안 주면 새로 만듦)")
    ap.add_argument("--eval-from", default=EVAL_FROM)
    ap.add_argument("--judge-only", action="store_true", help="만들지 않고 견주기만")
    ap.add_argument("--apply", action="store_true", help="교체한다 (사람이 직접)")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--json", help="검증 결과를 이 파일에 JSON 으로도 남긴다 (화면용)")
    a = ap.parse_args()

    cur = KIT / BUNDLE[a.kind]
    cur_meta = json.loads((cur / "meta.json").read_text(encoding="utf-8"))
    #   CSV 는 선택입니다. 없으면 DB 의 crop_price_train 을 읽습니다.
    csv = Path(a.csv) if a.csv else None
    if csv and not csv.exists():
        raise SystemExit(f"CSV 가 없습니다: {csv}")

    #   후보 정하기
    if a.cand:
        cand = KIT / a.cand
        if not cand.exists():
            raise SystemExit(f"후보 번들이 없습니다: {cand}")
    else:
        stamp = datetime.date.today().strftime("%Y%m%d")
        cand = KIT / f"{BUNDLE[a.kind]}_cand_{stamp}"

    #   후보 만들기 — 학습을 견주는 창 **앞에서** 끊는다
    if not a.judge_only and not a.cand:
        end = cand_train_end(a.eval_from)

        #   ★ 만들기 **전에** 건너뛴다 (2026-09-16 · 위 머리말 참조).
        #     현행이 이미 그 날짜까지 배웠으면 후보는 현행의 복사본이다.
        cur_end = up_to_date(cur_meta, end)
        if cur_end:
            rep = skip_report(a.kind, cur_end, end, a.eval_from)
            print(rep.text())
            if a.save:
                print("기록:", rep.save())
            if a.json:
                result_json(Path(a.json), a.kind, "", a.eval_from,
                            False, rep, [], skipped=True)
            return 0

        print(f"후보를 만듭니다. 학습 끝 {end} (견주는 창 {a.eval_from} 하루 전)")
        train_csv = csv or dump_csv(
            KIT / f"train_{datetime.date.today().strftime('%Y%m%d')}.csv")
        build(a.kind, train_csv, cur_meta, end, cand)

    if not cand.exists():
        raise SystemExit(f"후보 번들이 없습니다: {cand}\n  --cand 로 지정하거나 --judge-only 를 빼세요.")

    rep = Report("재학습검증", kind=a.kind)        # ★ 종류를 보고서에 박는다
    table: list = []
    ok = judge(rep, a.kind, csv, cur, cand, a.eval_from, table)
    print(rep.text())
    if a.save:
        print("기록:", rep.save())
    if a.json:
        result_json(Path(a.json), a.kind, cand.name, a.eval_from, ok, rep, table)

    if a.apply:
        if not ok:
            print("\n★ 검증을 통과하지 못했습니다. 교체하지 않습니다.")
            return 1
        apply(a.kind, cur, cand)
    elif ok:
        print("교체하려면 --apply 를 붙이세요. 자동으로 안 바꿉니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
