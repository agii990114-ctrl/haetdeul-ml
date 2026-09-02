# -*- coding: utf-8 -*-
"""배치 장애 조사 도우미 (2026-08-31).

## 무엇을 하나

일별 배치가 실패했을 때, **사람이 하던 조사를 대신**한다.

  1층 · 규칙   실패했나 · 며칠째인가 · 전달표가 얼마나 멈췄나  ← AI 없이 돈다
  2층 · AI     오류 원문에서 단서를 뽑아 코드를 뒤지고 원인을 씀
  3층 · 사람   읽고 판단하고 고친다

## 왜 1층을 규칙으로 두나

**AI 가 조용히 죽으면 "이상 없음" 처럼 보이기 때문이다.**
2026-08-27 에 경보 파일이 안 지워져 성공해도 "실패 중" 으로 보이던 일이
있었다. 같은 함정의 반대편이다.

**AI 가 실패해도 1층 보고서는 그대로 나온다.**

## 실제로 있었던 일 (이 도우미가 만들어진 이유)

    8/29 · 8/30 · 8/31 아침 9시   예측 실패
    매입 파트 전달표              8/28 이후 멈춤
    → 사흘 동안 아무도 몰랐다. 알림 파일은 떴지만 안 열어봤다.

원인은 오류 문구 한 줄에 다 있었다.

    입력에 feature 가 없습니다: ['_anchor_mix']

## 쓰는 법

    python agent/batch_agent.py             최근 실행을 본다
    python agent/batch_agent.py --run-id 28 특정 실행
    python agent/batch_agent.py --no-ai     규칙만 (AI 안 부름)
"""
from __future__ import annotations

import argparse
import datetime
import io
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import BAD, OK, WARN, Finding, Report, db          # noqa: E402
from mask import looks_leaky, mask                            # noqa: E402
from tools import SPEC, TOOLS                                 # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ALERT = ROOT / "진행기록" / "batch_logs" / "ALERT.txt"
MODEL = "gemini-3.7-flash"
MAX_TURNS = 14

# 일시적이라 다시 하면 되는 오류. 이 목록에 있으면 "구조적" 이 아니다.
TRANSIENT = ("timeout", "timed out", "시간 초과", "connection reset",
             "connection refused", "temporarily unavailable", "incompleteread",
             "remote end closed", "429", "500 server", "502", "503", "504")


# ── 1층 · 규칙 ──────────────────────────────────────────────────────

def gather(run_id: int | None) -> tuple[Report, dict]:
    """규칙만으로 사실을 모은다. AI 없이 끝까지 돈다."""
    rep = Report("배치장애조사")
    facts: dict = {}
    with db() as c:
        row = c.execute(
            "SELECT run_id, started_at::timestamp(0), status, n_ok, n_fail, note "
            "FROM batch_run " + ("WHERE run_id=%s " if run_id else "")
            + "ORDER BY run_id DESC LIMIT 1",
            (run_id,) if run_id else ()).fetchone()
        if not row:
            rep.add(Finding(WARN, "실행 기록이 없습니다"))
            return rep, facts
        rid, started, status, n_ok, n_fail, note = row
        facts["run_id"] = rid

        if status == "ok":
            rep.add(Finding(OK, f"run {rid} 정상 종료",
                            f"{started} · 성공 {n_ok} · 실패 {n_fail}"))
            return rep, facts

        #   ★ 아직 도는 중인 것을 실패로 보지 않는다 (2026-09-02 수정).
        #
        #   batch_run.status 는 넣을 때 'running' 으로 시작해 끝날 때
        #   'ok' / 'partial' / 'fail' 로 바뀐다. 예전 코드는 'ok' 만 걸러내고
        #   나머지를 전부 실패로 봤다. 그래서 **배치가 도는 중에 물어보면
        #   "구조적 오류로 보입니다" 라고 단정**했다.
        #
        #   실제로 걸렸다 — 2026-09-02 09:11:40 에 물었는데 배치가
        #   09:11:45 에 끝났다. 5초 차이로 잘못된 경보가 났다.
        #
        #   왜 고쳐야 하나: 잘못된 경보는 AI 조사(비용)를 부르고 ALERT.txt 에
        #   덧붙는다. 그게 매일 뜨면 사람이 알림을 무시하게 되고,
        #   그러면 진짜 이상도 같이 묻힌다. 우리가 이미 겪은 실패다.
        if status == "running":
            #   너무 오래 돌면 그건 그것대로 이상이다. 배치는 보통 10분쯤 걸린다.
            mins = None
            try:
                mins = c.execute(
                    "SELECT round(EXTRACT(EPOCH FROM (now() - started_at))/60) "
                    "FROM batch_run WHERE run_id=%s", (rid,)).fetchone()[0]
            except Exception:                                # noqa: BLE001
                pass
            if mins is not None and mins >= 45:
                rep.add(Finding(BAD, f"run {rid} 이 {int(mins)}분째 안 끝납니다",
                                f"{started} 시작 · 보통 10분쯤 걸립니다",
                                [("지금까지", f"성공 {n_ok} · 실패 {n_fail}")]))
            else:
                rep.add(Finding(OK, f"run {rid} 아직 도는 중입니다",
                                f"{started} 시작"
                                + (f" · {int(mins)}분 경과" if mins is not None else "")
                                + f" · 지금까지 성공 {n_ok} · 실패 {n_fail}"))
            return rep, facts

        # 실패한 단계와 오류 원문
        stages = c.execute(
            "SELECT seq, stage, ok, duration_s, message FROM batch_run_stage "
            "WHERE run_id=%s ORDER BY seq", (rid,)).fetchall()
        failed = [s for s in stages if not s[2]]
        fstage = failed[0][1] if failed else (note or "알 수 없음")
        fmsg = (failed[0][4] or "").strip() if failed else ""
        facts["stage"] = fstage
        facts["message"] = fmsg

        rep.add(Finding(BAD, f"run {rid} · '{fstage}' 단계에서 실패",
                        f"{started} · 성공 {n_ok} · 실패 {n_fail}",
                        [("오류 첫 줄", mask(fmsg.splitlines()[0])[:90] if fmsg else "-")]))

        # 며칠째 같은 단계가 실패하나
        #
        # ★★ 2026-08-31 수정 — **연속 횟수를 잘못 세고 있었다.**
        #
        #   예전에는 `note LIKE '%단계%'` 인 실패 run 을 **기록 전체에서 그냥
        #   세기만** 했다. 연속인지 보지 않고, 오류 내용이 같은지도 안 봤다.
        #
        #   실측 피해 (2026-08-31 무인 점검이 잡음):
        #     화면 표시     "같은 단계가 5번째 실패 · 연속 5회"
        #     실제          5건 중 원인이 3가지
        #                     _anchor_mix 없음      3건
        #                     DB 연결 끊김          1건 (run 8)
        #                     meta.json 없음        1건 (run 32)
        #                   게다가 중간에 성공한 run 이 둘(29·31) 있었다.
        #                   연속이 아니다.
        #
        #   부풀린 숫자는 "심각하다" 는 착각을 만들고, 그게 반복되면 사람이
        #   숫자를 안 믿게 된다. 오늘 아침 데이터 품질 오탐과 같은 문제다.
        #
        #   이제는 두 가지를 함께 본다.
        #     · **최근 run 부터 거꾸로** 훑어 성공을 만나면 멈춘다 (진짜 연속)
        #     · 오류 **첫 줄이 같은 것**만 센다 (같은 사고인지)
        recent = c.execute(
            "SELECT r.run_id, r.status, r.started_at::date, "
            "       (SELECT s.message FROM batch_run_stage s "
            "         WHERE s.run_id = r.run_id AND NOT s.ok ORDER BY s.seq LIMIT 1) "
            "  FROM batch_run r WHERE r.run_id <= %s "
            "   AND (r.stages_plan IS NULL OR r.stages_plan LIKE %s) "
            " ORDER BY r.run_id DESC LIMIT 60", (rid, f"%{fstage}%")).fetchall()
        head = (fmsg.splitlines()[0].strip() if fmsg else "")
        streak, same, first, broke = 0, 0, None, None
        for _r_id, st, d, msg in recent:
            if st != "fail":
                broke = d                # 여기서 성공했다 → 연속 끊김
                break
            streak += 1
            first = d
            if head and (msg or "").strip().splitlines()[:1] == [head]:
                same += 1
        facts["streak"] = streak
        facts["same_error"] = same
        if streak >= 2:
            detail = f"처음 실패한 날: {first}"
            if broke:
                detail += f"\n그 앞({broke})에는 성공한 실행이 있습니다."
            if same < streak:
                detail += (f"\n★ {streak}번 중 오류 문구가 같은 것은 {same}번입니다 — "
                           "나머지는 다른 사고입니다.")
            else:
                detail += "\n같은 오류가 이어집니다. 일시적 오류가 아닙니다."
            rep.add(Finding(BAD, f"'{fstage}' 가 {streak}번 연속 실패", detail,
                            [("연속 실패", f"{streak}회"),
                             ("그중 같은 오류", f"{same}회")]))

        # 일시적인가 구조적인가
        #
        # ★ 2026-08-31 — 이 판정은 **오류 문구의 낱말만 봅니다.**
        #   run 32 를 "다시 돌려도 같습니다" 로 판정했지만, 실제로는 폴더가
        #   잠깐 없었던 것이라 지금 돌리면 성공한다. 낱말로 맞히는 데는
        #   한계가 있으니, 단정하지 말고 **단정할 수 없다고 쓴다.**
        low = fmsg.lower()
        transient = any(t in low for t in TRANSIENT)
        facts["transient"] = transient
        #   이 판정은 오류 문구의 낱말만 본다. 단정할 수 없으니 제목을
        #   "~로 보입니다" 로 쓰고, 설명은 일시적일 때만 붙인다. 구조적
        #   쪽은 위 Finding 이 이미 오류 원문을 보여주므로 되풀이하지 않는다.
        rep.add(Finding(
            WARN,
            "일시적 오류로 보입니다" if transient else "구조적 오류로 보입니다",
            "연결·시간초과 같은 말이 있습니다. 다시 돌리면 풀릴 수 있습니다."
            if transient else ""))

    # 전달표가 얼마나 멈췄나 — 매입 파트에 직접 영향
    #   ★ **적재 시각**으로 잰다. 기준일(base_dt)로 재면 안 된다 —
    #     기준일은 중도매가 조사일 축이라 **정상일 때도 1~3일 뒤처진다.**
    #     실제로 오늘 09:35 에 정상 적재했는데 기준일 기준으로는
    #     "3일 멈춤" 으로 잘못 나왔다.
    #   ★★ 2026-08-31 수정 — **과거분 채워넣기에 속고 있었다.**
    #
    #     예전에는 `MAX(base_dt)` 와 `MAX(created_at)` 을 **각각 따로** 뽑았다.
    #     둘이 서로 다른 행에서 나올 수 있다.
    #
    #     실측 (2026-08-31 무인 점검이 잡음):
    #       12:21 검사 결과   "마지막 적재 11:11:33 · 0일 전 · 정상"
    #       그 행의 기준일     2025-12-31   ← 8개월 전 것을 채워넣은 행
    #       진짜 최신 예측     2026-08-28 기준 (09:35 적재)
    #
    #     오늘은 진짜 예측도 나갔으니 결과적으로 문제가 없었다. 하지만
    #     **오늘 예측이 실패한 날에 누가 과거분을 채워넣으면 "정상" 이라고
    #     말한다.** 08-27 에 겪은 "성공했는데 실패로 보이던" 사고의 정반대다.
    #
    #     이제 **가장 최근 기준일의 행**만 보고, 그 행이 언제 적재됐는지 잰다.
    #     기준일과 적재 시각이 반드시 같은 행에서 나온다.
    try:
        with db(service=True) as c:
            r = c.execute(
                "WITH latest AS ("
                "  SELECT base_dt FROM haetdeul.ml_price_forecasts"
                "   ORDER BY base_dt DESC LIMIT 1)"
                "SELECT f.base_dt::text,"
                "       MAX(f.created_at AT TIME ZONE 'Asia/Seoul')::timestamp(0)::text,"
                "       (CURRENT_DATE - MAX(f.created_at AT TIME ZONE 'Asia/Seoul')::date),"
                "       COUNT(*)"
                "  FROM haetdeul.ml_price_forecasts f"
                "  JOIN latest l ON l.base_dt = f.base_dt"
                " GROUP BY 1").fetchone()
        if r and r[1]:
            lag = int(r[2] or 0)
            facts["delivery_lag"] = lag
            base_gap = ((datetime.date.today() - datetime.date.fromisoformat(r[0])).days
                        if r[0] else None)
            rep.add(Finding(
                BAD if lag >= 2 else (WARN if lag == 1 else OK),
                f"매입 파트 전달표 — 최신 예측이 {lag}일 전에 적재됨",
                #   정상이면 아무 말도 안 한다. 제목에 이미 며칠 전인지 있다.
                ("예측이 안 나가면 매입 판단이 옛 값으로 이뤄집니다."
                 if lag >= 2 else ""),
                [("가장 최근 기준일", f"{r[0]} (오늘과 {base_gap}일 차 · 1~3일은 정상)"),
                 ("그 기준일이 적재된 시각", r[1]),
                 ("행수", f"{r[3]:,}행")]))
    except Exception as e:                                   # noqa: BLE001
        rep.add(Finding(WARN, "전달표 확인 실패", f"{type(e).__name__}"))

    return rep, facts


# ── 2층 · AI ────────────────────────────────────────────────────────

SYSTEM = """너는 농산물 가격 예측 시스템의 장애를 조사하는 도우미다.

## 하는 일
주어진 도구로 **스스로 조사해서** 고장 원인을 찾는다.
한 번에 하나씩 부르고, 결과를 보고 다음에 무엇을 볼지 정한다.

## 반드시 지킬 것
1. **추측을 사실처럼 말하지 마라.** 확인한 것만 근거로 든다.
2. **파일 이름·함수 이름·줄 번호를 지어내지 마라.** 도구로 본 것만 쓴다.
3. 모르면 "확인하지 못했다" 고 쓴다.
4. **고치지 마라.** 조사하고 설명만 한다. 명령을 실행하라고 시키지도 마라.
5. 초등학생도 알아듣게 쓴다. 전문 용어는 옆에 풀이를 붙인다.

## 조사 요령
· 오류 원문을 먼저 본다 (batch_stages)
· 문구에 나온 이름을 search_code 로 찾는다 ← 파일을 넘겨가며 읽지 마라
· 최근 변경(recent_changes)과 이어지는지 본다

## 끝낼 때
도구를 더 부르지 말고 아래 형식으로만 답한다.

원인: (한두 문장)
근거: (무엇을 보고 판단했나. 파일과 줄 번호)
영향: (무엇이 안 되고 있나)
확인못함: (조사했지만 확인 못 한 것. 없으면 '없음')
"""


def _key() -> str | None:
    v = os.environ.get("GEMINI_API_KEY")
    if v:
        return v
    p = ROOT / ".env"
    if not p.exists():
        return None
    for line in io.open(p, encoding="utf-8", errors="ignore"):
        if line.strip().startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    return None


def investigate(facts: dict, model: str, verbose: bool) -> tuple[str | None, list]:
    """AI 에게 조사를 시킨다. 실패하면 (None, ...) 을 돌려주고 조용히 넘어간다."""
    key = _key()
    if not key:
        return None, []
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None, []

    decls = []
    for s in SPEC:
        decls.append({
            "name": s["name"], "description": s["description"],
            "parameters": {"type": "object", "properties": {
                k: {"type": "string", "description": v}
                for k, v in s["params"].items()}}})

    client = genai.Client(api_key=key)
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        tools=[types.Tool(function_declarations=decls)])
    q = (f"run_id {facts.get('run_id')} 의 '{facts.get('stage')}' 단계가 "
         f"실패했다. 원인을 조사해줘.")
    contents = [types.Content(role="user", parts=[types.Part(text=q)])]
    used = []
    try:
        for _ in range(MAX_TURNS):
            r = None
            for attempt in range(4):
                try:
                    r = client.models.generate_content(model=model,
                                                       contents=contents, config=cfg)
                    break
                except Exception as e:                       # noqa: BLE001
                    m = str(e)
                    if ("503" in m or "429" in m or "UNAVAILABLE" in m) and attempt < 3:
                        time.sleep(8 * (attempt + 1))
                        continue
                    raise
            if r is None:
                return None, used
            cand = r.candidates[0]
            calls = [p.function_call for p in (cand.content.parts or [])
                     if getattr(p, "function_call", None)]
            if not calls:
                return (r.text or "").strip(), used
            contents.append(cand.content)
            replies = []
            for fc in calls:
                fn, args = TOOLS.get(fc.name), dict(fc.args or {})
                used.append(fc.name)
                if verbose:
                    print(f"    [AI] {fc.name}({args})")
                if fn is None:
                    res = f"그런 도구는 없습니다: {fc.name}"
                else:
                    try:
                        for k in ("limit", "run_id", "days", "start", "lines"):
                            if k in args:
                                try:
                                    args[k] = int(args[k])
                                except (TypeError, ValueError):
                                    pass
                        res = fn(**args)
                    except Exception as e:                   # noqa: BLE001
                        res = f"도구 실행 실패: {type(e).__name__}: {e}"
                res = mask(str(res))
                replies.append(types.Part.from_function_response(
                    name=fc.name, response={"result": res}))
            contents.append(types.Content(role="user", parts=replies))
        return None, used
    except Exception as e:                                   # noqa: BLE001
        # AI 가 죽어도 1층 보고서는 이미 완성돼 있다. 그게 요점이다.
        return f"(AI 조사 실패: {type(e).__name__})", used


def check_answer(text: str) -> list[str]:
    """AI 가 지어낸 파일 이름이 있는지 본다. 있으면 경고로 남긴다."""
    import re
    bad = []
    for n in set(re.findall(r"[\w/\\.-]+\.py", text or "")):
        base = n.replace("\\", "/").split("/")[-1]
        if not list(ROOT.rglob(base)):
            bad.append(n)
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description="배치 장애 조사")
    ap.add_argument("--run-id", type=int, default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--no-ai", action="store_true", help="규칙만 돌린다")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--append-alert", action="store_true",
                    help="결과를 ALERT.txt 에 덧붙인다 (배치에서 부를 때)")
    a = ap.parse_args()

    rep, facts = gather(a.run_id)
    print(rep.text())

    ai_text = None
    if not a.no_ai and rep.worst == BAD:
        print("[AI 조사 중] …")
        ai_text, used = investigate(facts, a.model, a.verbose)
        if ai_text:
            fake = check_answer(ai_text)
            print("─" * 70)
            print("[AI 조사 결과]")
            print(ai_text)
            print()
            print(f"  도구 {len(used)}번: {' → '.join(used)}")
            if fake:
                print(f"  ⚠ 존재하지 않는 파일을 언급했습니다: {fake}")
                print("     → 이 부분은 믿지 마세요.")
        else:
            print("  (AI 를 쓸 수 없어 규칙 결과만 남깁니다)")

    p = rep.save()
    if ai_text:
        with io.open(p, "a", encoding="utf-8") as f:
            f.write(chr(10) + "─" * 70 + chr(10) + "[AI 조사 결과]" + chr(10))
            f.write(ai_text + chr(10))
    print(f"[기록] {p}")

    if a.append_alert and rep.worst == BAD and ALERT.exists():
        try:
            with io.open(ALERT, "a", encoding="utf-8") as f:
                f.write(chr(10) + "─" * 60 + chr(10))
                f.write("[자동 조사]" + chr(10))
                f.write(rep.text() + chr(10))
                if ai_text:
                    f.write(ai_text + chr(10))
        except Exception:                                    # noqa: BLE001
            pass
    return 1 if rep.worst == BAD else 0


if __name__ == "__main__":
    raise SystemExit(main())
