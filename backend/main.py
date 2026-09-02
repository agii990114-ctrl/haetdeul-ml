# -*- coding: utf-8 -*-
"""화면에 값을 대주는 API  (2026-08-31)

## 왜 백엔드를 따로 두나

우리 데이터는 전부 PostgreSQL 에 있고, 접속 정보는 `.env` 에 있습니다.
브라우저가 DB 에 직접 붙으면 그 정보가 사용자 컴퓨터까지 나갑니다.
그래서 **DB 는 이 파이썬 프로그램만 붙고, 화면은 이 프로그램에게 묻습니다.**

mainproject 와 같은 방식입니다 — 화면(Next.js) + 백엔드(파이썬).
개발할 때는 `/api` 로 시작하는 주소를 화면 쪽이 백엔드로 넘겨줍니다.

## 이 API 가 지키는 것

**값을 만들지 않습니다.** DB 에 있는 것을 그대로 넘깁니다. 없으면 `null` 로
넘기고, 화면이 "없음" 이라고 씁니다. 0 으로 채우지 않습니다 —
**0 과 모름은 다릅니다.**

    없는 값을 0 으로 채우면 화면에서 "가격이 0원" 으로 보입니다.
    그건 빈 값이 아니라 틀린 값입니다.

## 띄우는 법

    pip install fastapi uvicorn "psycopg[binary]"
    python -m uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import datetime
import io
import os
import re
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="원가 캣쳐 ML 콘솔 API", version="0.1.0")

#   개발 중에는 화면이 3000 포트에서 뜬다. 와일드카드(*)를 쓰지 않는 이유는
#   나중에 인증이 붙었을 때 아무 페이지나 우리 API 를 부르게 되기 때문이다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

#   ★ 화면은 **운영 기록만** 봅니다 (2026-09-01 수정).
#
#     prediction_log 에는 세 가지가 섞여 있습니다.
#       ops_auc  (밑줄)   매일 배치가 남긴 진짜 운영 기록
#       ops-auc  (붙임표) 2026-08-25 하루에 몰아 돌린 실험 백테스트
#       dummy-v0          표 만들 때 넣은 가짜
#
#     처음엔 밑줄과 붙임표를 둘 다 넣었습니다. 그래서 화면 날짜 목록의
#     대부분이 실험 자료였고, 그것도 **규격 고정(08-27) 이전**이라
#     날마다 전혀 다른 곡선이 나왔습니다. 사용자가 "연관성이 없다" 고
#     한 것이 이것입니다.
#
#     한 글자(밑줄 vs 붙임표) 차이로 성격이 완전히 다릅니다.
#     실험 자료를 화면에 섞으면 보는 사람이 운영 성능으로 읽습니다.
OPS = ("ops_auc", "ops_whsl", "ops_rtl")

#   경락가 규격 혼합을 고친 시점. 이보다 **먼저 적재된 예측**은 서로 다른
#   포장 규격이 섞인 값으로 만든 것이라, 다른 날과 나란히 놓고 비교하면 안 된다.
#
#   ★ 지우지 않는다. 그중 2026-08-26 은 매입 파트에 실제로 나간 기록이다
#     (haetdeul 적재 08-27 15:10). 화면을 깔끔하게 하려고 실제 이력을
#     지우면 "그때 뭐라고 했나" 를 되짚을 근거가 사라진다.
#     대신 화면에 표시해서 보는 사람이 알게 한다.
SPEC_FIX_AT = "2026-08-28"
KIND_NM = {"auc": "경락가", "whsl": "중도매가", "rtl": "소매가"}
KIND_ROLE = {"auc": "매입 — 경매에서 사는 값",
             "whsl": "중도매 — 도매상이 파는 값",
             "rtl": "매도 — 소비자가 사는 값"}


def _env() -> dict:
    out: dict = {}
    p = ROOT / ".env"
    if p.exists():
        for line in io.open(p, encoding="utf-8-sig", errors="ignore"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip("'").strip('"')
    return out


def db(service: bool = False):
    import psycopg
    key = "TEST_DATABASE_URL" if service else "DATABASE_URL"
    url = os.environ.get(key) or _env().get(key)
    if not url:
        raise HTTPException(500, f"{key} 가 .env 에 없습니다.")
    return psycopg.connect(url, connect_timeout=15)


def rows(cur) -> list[dict]:
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def num(v):
    """Decimal 은 JSON 으로 못 나간다. None 은 None 으로 둔다 (0 으로 바꾸지 않는다)."""
    return None if v is None else float(v)


# ─────────────────────────────────────────────────────────── 상태

@app.get("/health")
def health():
    try:
        with db() as c, c.cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:                                   # noqa: BLE001
        raise HTTPException(503, f"DB 에 닿지 못했습니다: {type(e).__name__}")


@app.get("/meta")
def meta():
    """화면 머리말에 쓸 것 — 무엇을 예측하는지, 어떤 규격인지."""
    return {
        "kinds": [{"kind": k, "name": KIND_NM[k], "role": KIND_ROLE[k]} for k in KIND_NM],
        "items": ["배추", "무", "양파"],
        "spec": {"배추": "그물망·파렛트 10kg",
                 "무": "상자·파렛트 20kg (2018년 이전 18kg)",
                 "양파": "그물망·파렛트 15kg"},
        "market": "서울가락 · 특등급 · 원/kg",
        "note": "마늘은 뺐습니다 — 중도매가가 94%의 날에 전날과 같아 예측 문제가 아닙니다.",
    }


# ─────────────────────────────────────────────────────────── 예측

@app.get("/forecast/base-dates")
def base_dates(limit: int = Query(60, ge=1, le=400)):
    with db() as c, c.cursor() as cur:
        cur.execute(
            "SELECT base_dt, COUNT(*) AS n, COUNT(actual_prc) AS scored, "
            "       COUNT(DISTINCT item_nm) AS n_item, MIN(created_at) AS made_at "
            "  FROM prediction_log WHERE model_ver = ANY(%s) "
            " GROUP BY 1 ORDER BY 1 DESC LIMIT %s", (list(OPS), limit))
        return [{"base_dt": str(r["base_dt"]), "n": r["n"],
                 "scored": r["scored"], "n_item": r["n_item"],
                 #   규격을 고치기 전에 만든 예측인가. 화면이 표시만 하고
                 #   거르지는 않는다 — 실제로 나간 기록이라 남겨야 한다.
                 "pre_fix": str(r["made_at"])[:10] < SPEC_FIX_AT}
                for r in rows(cur)]


@app.get("/forecast")
def forecast(base_dt: str, kind: str = Query("auc", pattern="^(auc|whsl|rtl)$"),
             show_actual: bool = True):
    """한 기준일의 예측. 영업일 축(리드타임 1~18) 그대로 넘긴다.

    `actual` 은 대상일이 지나 채점된 것만 값이 있다. 아직 안 지났으면 `null`
    이고, 화면은 그 칸을 비워 둔다.

    ★ `show_actual=false` — 실제값을 빼고 넘긴다 (2026-08-31 지시).

      지금은 지난 날짜로 시연하니 정답이 이미 있지만, **실제 운영에서는
      예측을 낼 때 정답이 없습니다.** 시연 화면에 정답이 보이면 보는 사람이
      "이만큼 맞힌다" 로 읽는데, 그건 실제로 쓸 때의 모습이 아닙니다.

      끄면 `actual` 과 `err_pct` 를 **null 로 비웁니다.** 0 으로 바꾸지
      않습니다 — 0 과 모름은 다릅니다.
    """
    with db() as c, c.cursor() as cur:
        cur.execute(
            "SELECT p.item_nm, p.lead_biz_d, p.target_dt, p.unit, "
            "       p.anchor_prc, p.pred_prc, p.pred_lo, p.pred_hi, "
            "       p.actual_prc, p.abs_pct_err, p.gated, p.gate_reason, "
            "       p.model_ver, q.use_recommended, q.note "
            "  FROM prediction_log p "
            "  LEFT JOIN ref_prediction_quality q "
            "         ON q.target_kind = p.target_kind AND q.item_nm = p.item_nm "
            " WHERE p.base_dt = %s AND p.target_kind = %s AND p.model_ver = ANY(%s) "
            " ORDER BY p.item_nm, p.lead_biz_d", (base_dt, kind, list(OPS)))
        rs = rows(cur)
    if not rs:
        raise HTTPException(404, f"{base_dt} 의 {KIND_NM[kind]} 예측이 없습니다.")

    by: dict = {}
    for r in rs:
        by.setdefault(r["item_nm"], []).append({
            "lead": r["lead_biz_d"], "target_dt": str(r["target_dt"]),
            "anchor": num(r["anchor_prc"]), "pred": num(r["pred_prc"]),
            "lo": num(r["pred_lo"]), "hi": num(r["pred_hi"]),
            "actual": num(r["actual_prc"]) if show_actual else None,
            "err_pct": num(r["abs_pct_err"]) if show_actual else None,
            "gated": bool(r["gated"]), "gate_reason": r["gate_reason"],
        })
    out = []
    for item, rr in sorted(by.items()):
        head = next(x for x in rs if x["item_nm"] == item)
        out.append({"item": item, "unit": head["unit"], "model_ver": head["model_ver"],
                    "use_recommended": head["use_recommended"],
                    "quality_note": head["note"], "rows": rr})
    return {"base_dt": base_dt, "kind": kind, "kind_name": KIND_NM[kind],
            "role": KIND_ROLE[kind], "show_actual": show_actual, "items": out}


# ─────────────────────────────────────────────────────────── 정확도

@app.get("/accuracy")
def accuracy(min_lead: int = Query(3, ge=1, le=18), base_dt: str | None = None):
    """채점된 예측으로 잰 정확도.

    ★ 리드타임 3 미만은 기본으로 뺀다. 그 구간은 모델을 안 쓰고 앵커를 그대로
      내보내므로(게이트), 섞으면 모델 성적이 실제보다 좋아 보인다.
    """
    where = ["actual_prc IS NOT NULL", "lead_biz_d >= %s", "model_ver = ANY(%s)"]
    args: list = [min_lead, list(OPS)]
    if base_dt:
        where.append("base_dt = %s")
        args.append(base_dt)
    sql = (
        "SELECT target_kind, item_nm, COUNT(*) AS n, "
        "       SUM(ABS(actual_prc - pred_prc))   / NULLIF(SUM(actual_prc),0) AS model_wmape, "
        "       SUM(ABS(actual_prc - anchor_prc)) / NULLIF(SUM(actual_prc),0) AS anchor_wmape, "
        "       AVG(abs_pct_err) AS mape, "
        "       COUNT(*) FILTER (WHERE actual_prc BETWEEN pred_lo AND pred_hi)::numeric "
        "         / NULLIF(COUNT(*),0) AS band_hit "
        "  FROM prediction_log WHERE " + " AND ".join(where) +
        " GROUP BY 1,2 ORDER BY 1,2")
    with db() as c, c.cursor() as cur:
        cur.execute(sql, args)
        rs = rows(cur)
    out = []
    for r in rs:
        m, a = num(r["model_wmape"]), num(r["anchor_wmape"])
        out.append({
            "kind": r["target_kind"],
            "kind_name": KIND_NM.get(r["target_kind"], r["target_kind"]),
            "item": r["item_nm"], "n": r["n"],
            "model_wmape": m, "anchor_wmape": a, "mape": num(r["mape"]),
            "improve_pct": None if not m or not a else (1 - m / a) * 100,
            "band_hit": num(r["band_hit"]),
        })
    return {"min_lead": min_lead, "base_dt": base_dt, "rows": out,
            "caveat": "앵커 하나에 댄 값입니다. 더 센 baseline 이 있을 수 있습니다."}


@app.get("/accuracy/leadtime")
def accuracy_leadtime(kind: str = Query("auc", pattern="^(auc|whsl|rtl)$")):
    """리드타임이 멀수록 어떻게 되나. 게이트 구간(1~2)도 같이 보여준다."""
    with db() as c, c.cursor() as cur:
        cur.execute(
            "SELECT lead_biz_d, COUNT(*) AS n, "
            "       SUM(ABS(actual_prc-pred_prc))/NULLIF(SUM(actual_prc),0)   AS model_wmape, "
            "       SUM(ABS(actual_prc-anchor_prc))/NULLIF(SUM(actual_prc),0) AS anchor_wmape "
            "  FROM prediction_log "
            " WHERE target_kind=%s AND actual_prc IS NOT NULL AND model_ver = ANY(%s) "
            " GROUP BY 1 ORDER BY 1", (kind, list(OPS)))
        rs = rows(cur)
    out = []
    for r in rs:
        m, a = num(r["model_wmape"]), num(r["anchor_wmape"])
        out.append({"lead": r["lead_biz_d"], "n": r["n"], "model_wmape": m,
                    "anchor_wmape": a,
                    "improve_pct": None if not m or not a else (1 - m / a) * 100})
    return {"kind": kind, "kind_name": KIND_NM[kind], "rows": out}


@app.get("/quality-table")
def quality_table():
    """어떤 조합에 모델을 쓰고 어떤 조합은 앵커로 돌리는가."""
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT target_kind, item_nm, use_recommended, note "
                    "  FROM ref_prediction_quality ORDER BY 1,2")
        return [{"kind": r["target_kind"], "kind_name": KIND_NM.get(r["target_kind"]),
                 "item": r["item_nm"], "use": bool(r["use_recommended"]),
                 "note": r["note"]} for r in rows(cur)]


# ─────────────────────────────────────────────────────────── 데이터 품질

_QCACHE: dict = {}


@app.get("/quality")
def quality(days: int = Query(180, ge=30, le=1500)):
    """데이터 품질 agent 를 돌려 결과를 넘긴다.

    DB 를 훑으므로 10초쯤 걸린다. 같은 조건이면 10분간 기억해 둔다 —
    화면을 새로 그릴 때마다 다시 돌 이유가 없다.
    """
    now = datetime.datetime.now()
    hit = _QCACHE.get(days)
    if hit and (now - hit[0]).total_seconds() < 600:
        return hit[1]

    import sys
    p = str(ROOT / "agent")
    if p not in sys.path:
        sys.path.insert(0, p)
    import quality_agent as qa                               # noqa: PLC0415
    from core import WARN, Finding, Report                   # noqa: PLC0415

    rep = Report("데이터품질")
    with qa.db() as cn, cn.cursor() as cur:
        for fn in (qa.check_grade_order, qa.check_intraday,
                   qa.check_series_health, qa.check_target_anchor):
            try:
                rep.add(fn(cur, days))
            except Exception as e:                           # noqa: BLE001
                rep.add(Finding(WARN, f"{fn.__name__} 점검 실패",
                                f"{type(e).__name__}: {e}"))
    out = {"name": rep.name, "verdict": rep.worst, "days": days,
           "at": rep.started.strftime("%Y-%m-%d %H:%M:%S"),
           "findings": [asdict(f) for f in rep.findings]}
    _QCACHE[days] = (now, out)
    return out


@app.get("/agent/explain")
def agent_explain(base_dt: str, item: str, lead: int,
                  kind: str = Query("auc", pattern="^(auc|whsl|rtl)$"),
                  show_actual: bool = True):
    """예측 하나를 왜 그렇게 냈는지 설명한다 (규칙만).

    ★ AI 는 부르지 않는다. 화면에서 점을 누를 때마다 외부 API 를 부르면
      느리고 돈이 든다. 규칙만으로도 다섯 조각이 다 나온다.
    """
    import sys
    p = str(ROOT / "agent")
    if p not in sys.path:
        sys.path.insert(0, p)
    import forecast_agent as fa                              # noqa: PLC0415

    #   화면에서는 한계(지난 오차)를 빼고 보여준다 (2026-08-31 지시).
    #   수치 자체는 컬럼정의서와 score_predictions.py 에 그대로 남아 있다.
    rep, facts = fa.explain(base_dt, item, kind, int(lead),
                            with_limit=False, with_actual=show_actual)
    return {"name": rep.name, "verdict": rep.worst,
            "at": rep.started.strftime("%Y-%m-%d %H:%M:%S"),
            "base_dt": facts.get("base_dt"), "item": item, "kind": kind, "lead": lead,
            "findings": [asdict(f) for f in rep.findings]}


@app.get("/agent/batch")
def agent_batch(run_id: int | None = None):
    """배치 조사 agent 의 **규칙 부분**만 돌린다.

    ★ AI 조사(`investigate`)는 부르지 않는다. 화면이 그릴 때마다 외부 API 를
      부르면 느리고 돈이 들고, 무엇보다 **AI 가 죽으면 화면이 빈다.**
      규칙은 항상 끝까지 돌므로 화면에는 늘 무언가 뜬다.
    """
    import sys
    p = str(ROOT / "agent")
    if p not in sys.path:
        sys.path.insert(0, p)
    import batch_agent as ba                                 # noqa: PLC0415

    rep, facts = ba.gather(run_id)
    return {"name": rep.name, "verdict": rep.worst,
            "at": rep.started.strftime("%Y-%m-%d %H:%M:%S"),
            "run_id": facts.get("run_id"),
            "findings": [asdict(f) for f in rep.findings]}


# ─────────────────────────────────────────────────────────── agent 기록

AGENT_DIR = ROOT / "진행기록" / "agent_logs"

#   파일 이름만 받고 경로는 절대 받지 않는다. `../../.env` 같은 게 들어오면
#   그대로 읽어서 접속 정보가 브라우저로 나간다. 이름 모양을 통째로 못박는다.
_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(_\d{6})?_[^\\/:*?\"<>|]{1,40}\.(txt|md)$")


def _verdict_of(text: str) -> str | None:
    """규칙 agent 보고서 첫머리의 '판정: X' 를 읽는다. 없으면 None."""
    for line in text.splitlines()[:6]:
        if line.startswith("판정:"):
            return line.split(":", 1)[1].strip()
    return None


@app.get("/agent/history")
def agent_history(limit: int = Query(120, ge=1, le=600)):
    """저장된 agent 보고서를 날짜별로 묶어 넘긴다.

    파일이 곧 기록이다. DB 에 또 넣지 않는다 — 두 곳에 있으면 갈라진다.
    """
    if not AGENT_DIR.exists():
        return {"dates": []}
    out: dict = {}
    for p in sorted(AGENT_DIR.iterdir(), reverse=True)[:limit]:
        if not p.is_file() or not _NAME_RE.match(p.name):
            continue
        stem = p.stem
        date = stem[:10]
        rest = stem[11:]
        if p.suffix == ".md":
            kind, time_s = rest or "claude_check", None
        else:
            time_s = rest[:6] if rest[:6].isdigit() else None
            kind = rest[7:] if time_s else rest
        try:
            head = io.open(p, encoding="utf-8", errors="replace").read(2000)
        except OSError:
            continue
        out.setdefault(date, []).append({
            "file": p.name, "kind": kind,
            "time": f"{time_s[:2]}:{time_s[2:4]}:{time_s[4:6]}" if time_s else None,
            "verdict": _verdict_of(head),
            "is_claude": p.suffix == ".md",
            "bytes": p.stat().st_size,
        })
    return {"dates": [{"date": d, "reports": sorted(
        rs, key=lambda r: (r["time"] or "99"), reverse=True)}
        for d, rs in sorted(out.items(), reverse=True)]}


@app.get("/agent/report")
def agent_report(file: str):
    """보고서 한 개의 내용. 이름 모양을 통과한 것만 읽는다."""
    if not _NAME_RE.match(file):
        raise HTTPException(400, "읽을 수 없는 파일 이름입니다.")
    p = AGENT_DIR / file
    #   심볼릭 링크 등으로 밖을 가리킬 수 있어 실제 경로까지 확인한다.
    if not p.is_file() or AGENT_DIR.resolve() not in p.resolve().parents:
        raise HTTPException(404, f"그런 보고서가 없습니다: {file}")
    return {"file": file, "text": io.open(p, encoding="utf-8", errors="replace").read(),
            "is_claude": p.suffix == ".md"}


# ─────────────────────────────────────────────────────────── 배치

@app.get("/batch/recent")
def batch_recent(limit: int = Query(15, ge=1, le=100)):
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT run_id, started_at, finished_at, status, host, "
                    "       stages_plan, n_ok, n_fail, note "
                    "  FROM batch_run ORDER BY run_id DESC LIMIT %s", (limit,))
        runs = rows(cur)
        ids = [r["run_id"] for r in runs]
        stages: dict = {}
        if ids:
            cur.execute("SELECT run_id, seq, stage, ok, duration_s, message "
                        "  FROM batch_run_stage WHERE run_id = ANY(%s) "
                        " ORDER BY run_id DESC, seq", (ids,))
            for s in rows(cur):
                stages.setdefault(s["run_id"], []).append({
                    "seq": s["seq"], "stage": s["stage"], "ok": s["ok"],
                    "sec": num(s["duration_s"]), "message": s["message"]})
    return [{"run_id": r["run_id"],
             "started_at": r["started_at"].isoformat() if r["started_at"] else None,
             "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
             "status": r["status"], "host": r["host"], "plan": r["stages_plan"],
             "n_ok": r["n_ok"], "n_fail": r["n_fail"], "note": r["note"],
             "stages": stages.get(r["run_id"], [])} for r in runs]


# ─────────────────────────────────────────────────────────── 전달표

@app.get("/delivery")
def delivery(base_dt: str | None = None):
    """매입 파트가 실제로 보는 표. 달력 날짜 축(D+1~D+18)이다.

    우리는 장이 서는 날만 세고, 저쪽은 달력 날짜를 그대로 센다. 장이 안 서는
    날은 가장 가까운 예측으로 채우고 `is_filled` 를 켠다.
    """
    with db(service=True) as c, c.cursor() as cur:
        cur.execute("SELECT base_dt, COUNT(*) n, MIN(offset_days) mn, MAX(offset_days) mx "
                    "  FROM haetdeul.ml_price_forecasts GROUP BY 1 ORDER BY 1 DESC")
        avail = [{"base_dt": str(r["base_dt"]), "n": r["n"],
                  "off_min": r["mn"], "off_max": r["mx"]} for r in rows(cur)]
        if not avail:
            raise HTTPException(404, "전달표가 비어 있습니다.")
        if not base_dt:
            base_dt = avail[0]["base_dt"]
        cur.execute("SELECT item_nm, target_kind, offset_days, target_dt, "
                    "       predicted, lower, upper, current_price, unit, "
                    "       is_filled, is_gated, gate_reason, src_lead_biz_d, "
                    "       market_name, grade_name, spec_desc, use_recommended "
                    "  FROM haetdeul.ml_price_forecasts WHERE base_dt=%s "
                    " ORDER BY target_kind, item_nm, offset_days", (base_dt,))
        rs = rows(cur)
    out = []
    for r in rs:
        d = {}
        for k, v in r.items():
            d[k] = str(v) if isinstance(v, datetime.date) else num(v) if hasattr(v, "as_tuple") else v
        out.append(d)
    return {"base_dt": str(base_dt), "available": avail, "rows": out}
