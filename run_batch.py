# -*- coding: utf-8 -*-
"""
원가 캣쳐 — 일별 배치
======================
수집 → 재생성 → 추론 → 적재 → 채점을 순서대로 돌린다.
어느 단계든 실패하면 **거기서 멈춘다.** 반쯤 돌린 상태로 예측을 내보내지 않는다.

    python run_batch.py --dry-run            # 무엇을 돌릴지만 보여준다
    python run_batch.py                      # 전체 (수집은 오래 걸린다)
    python run_batch.py --stages rebuild,predict,load,score
    python run_batch.py --skip collect_volume,collect_weather

단계
----
    collect_*   수집 5종. 각각 독립이라 하나가 실패해도 나머지는 돈다
                (단 --strict 를 주면 하나라도 실패 시 중단)
    rebuild     DBEAVER_run_v5.sql — crop_price_train + predict_input 재생성
    predict     predict_input 최신 기준일로 3타겟 추론
    load        예측 → prediction_log
    score       대상일 지난 예측에 실제값 채우기

매일은 추론만 한다
------------------
학습은 이 배치에 없다. 월 1회 또는 드리프트 감지 시 사람이 돌린다.
매일 학습하면 예측이 요동쳐 "왜 어제와 다르냐" 에 답할 수 없다.

신선도 가드
-----------
추론 전에 앵커가 얼마나 낡았는지 잰다. 임계를 넘으면 **예측을 만들지 않는다.**
몇 달 전 가격으로 "오늘의 예측" 을 내놓는 것이 가장 나쁜 사고이고,
그건 예외가 아니라 그럴듯한 숫자로 나온다.

임계는 **달력상 마지막 조사일** 기준이다. 달력일로 재면 주말·연휴마다 오탐이 난다.
"""
import argparse
import datetime
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
KIT = ROOT / "ML" / "20260824" / "ml_train_kit_2"
COL = ROOT / "데이터 수집"
LOGDIR = ROOT / "진행기록" / "batch_logs"

# 운영에 쓸 모델 번들. 바꾸려면 여기만 고친다.
MODELS = {"auc": "ops_auc", "whsl": "ops_whsl", "rtl": "ops_rtl"}

# ── 그림자 실행 (2026-09-01) ──────────────────────────────────────────
#   분위수 회귀로 예측 구간을 만드는 새 번들을 **옆에서 같이** 돌린다.
#   왜 이렇게 하나:
#     · 점 예측은 옛것과 완전히 같아야 한다. 매일 그걸 확인한다
#     · 구간이 실제 운영 자료(predict_input)에서도 제대로 나오는지 본다
#     · ★ prediction_log 에 **넣지 않는다.** 2026-09-01 에 실험 기록이
#       운영 기록과 섞여 매입 파트에 틀린 수치를 보낸 사고가 있었다
#     · 매입 파트 필터가 model_ver = ANY('ops_auc','ops_whsl','ops_rtl') 로
#       **정확히 일치**만 받으므로, 이름을 바꿔 적재하면 저쪽에서 조용히
#       0건이 된다. 그래서 적재 자체를 안 한다
#   며칠 돌려 문제가 없으면 번들을 같은 이름으로 교체한다(이름은 안 바꾼다).
SHADOW = {"auc": "ops_auc_q", "whsl": "ops_whsl_q"}
SHADOW_LOG = ROOT / "실험결과" / "shadow_quantile.csv"

# 앵커가 조사일 기준 며칠 이상 밀리면 추론을 멈출지
MAX_SURVEY_LAG = 3


def dsn():
    for raw in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            os.environ.setdefault(k.strip(), v)
    u = os.environ.get("DATABASE_URL")
    if not u:
        sys.exit(".env 에 DATABASE_URL 이 없습니다.")
    return u


# ── 단계 정의 ────────────────────────────────────────────────────────
#   (이름, 설명, 작업디렉터리, 명령)
def _auction_gaps(conn, today, days=14):
    """최근 N일 개장일 중 경락가 행이 없는 날."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.dt
              FROM ref_calendar c
             WHERE c.is_open
               AND c.dt BETWEEN %s::date - %s AND %s::date - 1
               AND NOT EXISTS (SELECT 1 FROM auction_prices_daily a
                                WHERE a.auction_date = c.dt)
             ORDER BY c.dt""", (today, days, today))
        return [r[0] for r in cur.fetchall()]


def check_auction_gap(conn, log, today):
    """개장일인데 경락가가 비었으면 **다시 받아 채운다.**

    ★ 2026-08-31 에 겪은 사고.

        run 25 (8/29 배치)  요청 2026-08-28(금·개장일)
                            → API 호출 0회 → 0행 적재 → status: ok

      수집기가 8/28 에 빈 결과를 캐시에 굳혔고, 그 뒤로는 API 를 안 부르고
      그 빈 값을 돌려줬다 (`cache_hit rows: 0`). 하루가 통째로 비었는데
      배치는 사흘 내리 "성공" 이었다. 매입 파트가 "적재가 늦는다" 고
      물어봐서 찾았다 — 지연을 세는 눈으로는 **구멍**이 안 보인다.

    그래서 종료코드를 믿지 않고 **표를 직접 본다.**
    "실패했다는 말" 보다 "결과가 없다는 사실" 이 더 믿을 만하다.

    ## 왜 여기서는 자동으로 다시 받아도 되나

    두 작업의 성격이 다르다.

        rebuild(v5)    표를 통째로 비우고 다시 채운다 (TRUNCATE)
                       → 중간에 죽으면 데이터가 날아간다. 자동 재실행 금지
        collect(경락가) 날짜 하나를 받아 UPSERT 한다
                       → 몇 번을 돌려도 같은 결과. 지우는 게 없다

    `--force` 로 캐시를 무시해야 한다. 그냥 다시 돌리면 굳은 빈 값을
    또 받는다 (그래서 사흘 동안 안 고쳐졌다).

    ## 무한정 다시 받지 않는다

    `ref_calendar` 가 개장이라고 해도 실제로는 쉬었을 수 있다. 비정기
    휴장이 연 1.3회 있고 override 표로 관리한다 (§5.8). 다시 받았는데도
    0건이면 그건 수집 실패가 아니라 **달력이 틀린 것**일 수 있으므로,
    한 번만 시도하고 사람에게 넘긴다.
    """
    try:
        gaps = _auction_gaps(conn, today)
    except Exception as e:                                   # noqa: BLE001
        msg = "경락가 구멍 검사 실패: %s" % type(e).__name__
        log.write(msg + chr(10))
        return True, msg

    if not gaps:
        return True, "최근 14일 개장일 중 빠진 날 없음"

    print("    ★ 빠진 개장일 %d일 — 다시 받습니다: %s"
          % (len(gaps), " · ".join(str(d) for d in gaps)))
    log.write("빠진 개장일: %s%s" % (gaps, chr(10)))

    #   ★★ 수집기를 부르기 전에 **반드시 트랜잭션을 닫는다.**
    #
    #     2026-08-31 첫 시험에서 교착을 만들었다. 위 SELECT 가 트랜잭션을
    #     열어둔 채였고, 수집기가 별도 프로세스로 붙어
    #     `CREATE TABLE IF NOT EXISTS auction_prices_daily` 를 하려다
    #     그 표의 잠금을 기다렸다. 서로 12분 넘게 멈췄다.
    #
    #         16578  idle in transaction   ← 이 검사
    #         16579  active · Lock 대기    ← 수집기
    #
    #     읽기만 했으니 commit 해도 바뀌는 것이 없다. 잠금만 놓는다.
    conn.commit()

    cwd = COL / "경락가 수집" / "auction_collector_handoff"
    filled, still = [], []
    for d in gaps:
        cmd = [PY, "-m", "auction_collector", "collect",
               "--start", str(d), "--end", str(d),
               "--load-postgres", "--allow-backfill", "--force"]
        ok, tail = run(cmd, cwd, log, timeout=1800)
        log.write("  재수집 %s ok=%s%s" % (d, ok, chr(10)))
        (filled if ok else still).append(d)

    # 받고 나서 **다시 표를 본다.** 명령이 성공했다는 말은 안 믿는다.
    #   수집기가 넣은 것을 보려면 새 트랜잭션이어야 한다.
    try:
        conn.commit()
        left = _auction_gaps(conn, today)
    except Exception:                                        # noqa: BLE001
        left = still

    if not left:
        msg = "빠진 개장일 %d일을 다시 받아 채웠습니다: %s" % (
            len(gaps), " · ".join(str(d) for d in gaps))
        log.write(msg + chr(10))
        return True, msg

    lines = ["★ 다시 받았는데도 비어 있는 개장일 %d일: %s"
             % (len(left), " · ".join(str(d) for d in left))]
    if filled:
        lines.append("  (채운 날: %s)" % " · ".join(str(d) for d in filled))
    lines.append("  원천에 자료가 없습니다. 둘 중 하나입니다:")
    lines.append("   · 그날 실제로 쉬었다  → ref_calendar override 에 넣으세요")
    lines.append("   · 원천 API 가 늦었다  → 내일 배치가 다시 시도합니다")
    msg = chr(10).join(lines)
    log.write(msg + chr(10))
    return False, msg

# ── 다른 수집기의 구멍 검사 (2026-08-31) ────────────────────────────────────
#
#   경락가에서 하루가 통째로 빠진 걸 사흘 뒤에야 찾았다. 같은 일이 다른
#   수집기에서 나면 또 못 잡는다. 그래서 셋을 더 붙인다.
#
#   ★ "언제 데이터가 있어야 하는가" 는 짐작하지 않고 실측으로 정했다
#     (2026-08-31 · 최근 21일 관찰).
#
#       도·소매   ref_calendar.is_survey 인 날에만 있다 (토·일 없음)
#       반입량    ref_calendar.is_open 인 날에 5행 (5품목). 당일도 들어온다
#       기상      매일. 원천이 전일(D-1)까지만 준다
#
#   ★ 자동으로 다시 받는 것은 **싸고 안전한 것만** 한다.
#       도·소매   collect_kamis.py --start --end   → 자동 (가볍다)
#       기상      fetch_asos.py 시작 끝 --load-db  → 자동 (구간이 좁으면 가볍다)
#       반입량    농넷 스크래핑 20~25분           → **알리기만** 한다.
#                 배치가 두 배로 길어져 다음 단계가 밀린다. 사람이 판단할 일
#
#   되돌리는 작업이 아니라 **덮어쓰는 작업**이라 여러 번 돌려도 안전하다.
#   (v5 rebuild 처럼 표를 비우는 것과 성격이 다르다 — §2 참조)

GAP_CHECKS = {
    "collect_price": dict(
        label="도·소매",
        sql="""SELECT c.dt FROM ref_calendar c
                WHERE c.is_survey AND c.dt BETWEEN %s::date - %s AND %s::date - 1
                  AND NOT EXISTS (SELECT 1 FROM veg_daily_price_raw v
                                   WHERE v.exmn_ymd = c.dt)
                ORDER BY c.dt""",
        cwd=("중도매, 소매가",),
        cmd=lambda d1, d2: ["collect_kamis.py", "--start", str(d1), "--end", str(d2)],
        auto=True),
    "collect_volume": dict(
        label="반입량",
        sql="""SELECT c.dt FROM ref_calendar c
                WHERE c.is_open AND c.dt BETWEEN %s::date - %s AND %s::date - 1
                  AND NOT EXISTS (SELECT 1 FROM daily_volume v
                                   WHERE v.base_date = c.dt)
                ORDER BY c.dt""",
        cwd=("일일 산출량",),
        cmd=None,
        auto=False),                      # 스크래핑 20~25분. 알리기만
    "collect_weather": dict(
        label="기상",
        sql="""SELECT d.dt FROM generate_series(%s::date - %s, %s::date - 2,
                                                '1 day') AS d(dt)
                WHERE NOT EXISTS (SELECT 1 FROM weather_asos_raw w
                                   WHERE w."tm"::date = d.dt)
                ORDER BY d.dt""",         # 원천이 전일까지라 -2 부터 본다
        cwd=("기상데이터",),
        cmd=lambda d1, d2: ["fetch_asos.py", d1.strftime("%Y%m%d"),
                            d2.strftime("%Y%m%d"), "--load-db", "--no-csv"],
        auto=True),
}


def check_source_gap(conn, log, today, stage, days=14):
    """수집기가 성공이라 해도 표에 그날 행이 있는지 본다."""
    spec = GAP_CHECKS.get(stage)
    if not spec:
        return True, ""
    try:
        with conn.cursor() as cur:
            cur.execute(spec["sql"], (today, days, today))
            gaps = [r[0] for r in cur.fetchall()]
    except Exception as e:                                   # noqa: BLE001
        msg = "%s 구멍 검사 실패: %s" % (spec["label"], type(e).__name__)
        log.write(msg + chr(10))
        return True, msg

    if not gaps:
        return True, "%s — 최근 %d일 빠진 날 없음" % (spec["label"], days)

    lst = " · ".join(str(d) for d in gaps)
    if not spec["auto"]:
        msg = ("★ %s 가 빠진 날 %d일: %s%s  자동 재수집은 안 합니다 "
               "(스크래핑 20~25분). 손으로 돌리세요." % (
                   spec["label"], len(gaps), lst, chr(10)))
        log.write(msg + chr(10))
        return False, msg

    print("    ★ %s 빠진 날 %d일 — 다시 받습니다: %s" % (spec["label"], len(gaps), lst))
    #   ★ 수집기를 부르기 전에 트랜잭션을 닫는다. 안 그러면 교착이 난다
    #     (2026-08-31 경락가 검사에서 12분 멈춘 적 있음).
    conn.commit()

    cwd = COL.joinpath(*spec["cwd"])
    ok, _tail = run([PY] + spec["cmd"](gaps[0], gaps[-1]), cwd, log, timeout=1800)
    log.write("%s 재수집 ok=%s%s" % (spec["label"], ok, chr(10)))

    try:
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(spec["sql"], (today, days, today))
            left = [r[0] for r in cur.fetchall()]
    except Exception:                                        # noqa: BLE001
        left = gaps

    if not left:
        msg = "%s 빠진 날 %d일을 다시 받아 채웠습니다: %s" % (spec["label"], len(gaps), lst)
        log.write(msg + chr(10))
        return True, msg

    msg = ("★ %s — 다시 받았는데도 비어 있는 날 %d일: %s%s"
           "  원천에 자료가 없거나 달력이 틀렸습니다." % (
               spec["label"], len(left), " · ".join(str(d) for d in left), chr(10)))
    log.write(msg + chr(10))
    return False, msg

STAGES = [
    ("collect_auction", "경락가 증분 수집 + 적재",
     COL / "경락가 수집" / "auction_collector_handoff",
     [PY, "-m", "auction_collector", "update", "--load-postgres"]),
    ("collect_price", "도·소매 증분 수집 + 적재",
     COL / "중도매, 소매가", [PY, "collect_kamis.py"]),
    ("collect_weather", "기상 ASOS 수집",
     COL / "기상데이터", None),          # 기간이 동적이라 아래에서 만든다
    ("collect_volume", "반입량 스크래핑 (느림 · 20~25분)",
     COL / "일일 산출량", None),
    ("collect_econ", "경제변수 수집 + 적재",
     COL / "경제 지표", None),
    ("rebuild", "v5 재생성 (crop_price_train + predict_input)", ROOT, None),
    ("predict", "3타겟 추론", KIT, None),
    # 그림자는 load 앞에 둔다. 적재는 운영 것만 한다.
    ("shadow", "분위수 번들 그림자 실행 (적재 안 함)", KIT, None),
    ("load", "예측 → prediction_log", KIT, None),
    ("score", "실제값 채점", KIT, None),
    # 매입 파트 DB 로 넘기기 (2026-08-27). 영업일 -> 달력일 변환이 여기서 일어난다.
    # test DB 접속이 없으면 스스로 건너뛴다 (TEST_DATABASE_URL).
    ("push", "예측 -> 매입 파트 DB", ROOT / "연동",
     [PY, "push_forecast.py", "--commit"]),
]
NAMES = [s[0] for s in STAGES]


# 일시적 오류로 볼 문구 - 이 목록에 걸릴 때만 다시 시도한다 (2026-08-27)
#   좁게 잡는다. "실패했으니 일단 다시" 는 상황을 악화시킨다.
#   여기 없는 오류는 재시도하지 않고 그대로 보고한다.
TRANSIENT = (
    "timeout", "timed out", "시간 초과",
    "connection reset", "connection refused", "connection aborted",
    "connection timeout", "커넥션",
    "incompleteread", "remote end closed", "temporarily unavailable",
    "429", "500 server", "502", "503", "504",
    "eof occurred",
)
RETRY_MAX = 2            # 단계당 재시도 횟수
RETRY_WAIT = (30, 120)   # 대기(초). 늘려가며 기다린다
RETRY_BUDGET = 3         # 실행 전체 상한 - 무한 루프 방지
_retry_used = 0


def is_transient(text):
    t = (text or "").lower()
    return any(k in t for k in TRANSIENT)


def run(cmd, cwd, log, timeout=None, retry=True):
    """한 명령을 돌리고 (성공여부, 마지막 출력) 반환.

    **일시적 네트워크 오류만 다시 시도한다** (2026-08-27 추가).
    그날 두 번 겪었다 - 09:00 배치가 connection timeout 으로 추론에서 멈춰
    9시간 동안 예측이 없었고, 50분짜리 수집이 마지막에 IncompleteRead 로
    죽었다. 둘 다 한 번만 다시 했으면 끝날 일이었다.

    ▣ 작업 스케줄러의 "실패 시 다시 시작" 은 이걸 못 잡는다.
      그 설정은 **작업이 시작되지 못했을 때** 동작하고, 프로그램이 0 아닌
      종료 코드로 끝나는 것은 "정상 완료" 로 처리한다. 실제로 08-27 09:00
      실패(RestartCount 2 설정됨)에서 재시작이 일어나지 않았다.
      그래서 재시도는 여기, 우리 코드 안에 있어야 한다.

    ▣ rebuild 는 이 함수를 쓰지 않는다 (do_rebuild 별도). 맨 앞에서
      TRUNCATE 하므로 자동 재시도 대상이 아니다.
    """
    global _retry_used
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    attempt = 0
    while True:
        t0 = time.time()
        try:
            p = subprocess.run(cmd, cwd=str(cwd), env=env, timeout=timeout,
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            out = (p.stdout or "") + (p.stderr or "")
            ok = p.returncode == 0
        except subprocess.TimeoutExpired:
            out, ok = "시간 초과 (%s초)" % timeout, False
        log.write(out)
        log.flush()

        may_retry = (retry and not ok and attempt < RETRY_MAX
                     and _retry_used < RETRY_BUDGET and is_transient(out))
        if not may_retry:
            lines = [l for l in out.strip().split(chr(10))[-4:] if l.strip()]
            tail = chr(10).join(lines)
            if attempt:
                tail += chr(10) + "  (재시도 %d회 후)" % attempt
            return ok, tail + chr(10) + "  (%.0f초)" % (time.time() - t0)

        wait = RETRY_WAIT[min(attempt, len(RETRY_WAIT) - 1)]
        attempt += 1
        _retry_used += 1
        msg = "!! 일시적 오류로 보임 - %d초 뒤 재시도 (%d/%d · 전체 %d/%d)" % (
            wait, attempt, RETRY_MAX, _retry_used, RETRY_BUDGET)
        print("    " + msg)
        log.write(chr(10) + msg + chr(10))
        log.flush()
        time.sleep(wait)


def run_begin(conn, plan):
    """실행 시작을 batch_run 에 남기고 run_id 를 돌려준다.

    자동 실행을 걸면 사람이 로그 파일을 안 본다. DB 에 있어야 대시보드가 보고,
    "어제 돌았나" 를 이력으로 답할 수 있다.
    """
    import socket
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO batch_run (host, stages_plan) VALUES (%s, %s) "
                        "RETURNING run_id", (socket.gethostname(), ",".join(plan)))
            rid = cur.fetchone()[0]
        conn.commit()
        return rid
    except Exception as e:                                   # noqa: BLE001
        # 기록 실패가 배치를 멈추면 안 된다. 배치가 본업이다.
        conn.rollback()
        print("  [주의] batch_run 기록 실패 — 배치는 계속합니다: %s" % str(e)[:120])
        return None


def stage_log(conn, rid, seq, stage, ok, secs, msg):
    if rid is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO batch_run_stage "
                        "(run_id, seq, stage, ok, duration_s, message) "
                        "VALUES (%s,%s,%s,%s,%s,%s)",
                        (rid, seq, stage, ok, round(secs, 1), (msg or "")[:2000]))
        conn.commit()
    except Exception:                                        # noqa: BLE001
        conn.rollback()


def run_end(conn, rid, done, failed, stopped):
    if rid is None:
        return
    st = "fail" if stopped else ("partial" if failed else "ok")
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE batch_run SET finished_at=now(), status=%s, "
                        "n_ok=%s, n_fail=%s, note=%s WHERE run_id=%s",
                        (st, len(done), len(failed),
                         ("실패: " + ",".join(failed)) if failed else None, rid))
        conn.commit()
    except Exception:                                        # noqa: BLE001
        conn.rollback()


def survey_lag(conn):
    """달력상 마지막 조사일 대비 앵커가 며칠 밀렸나.

    달력일로 재면 주말·연휴마다 오탐이 난다. 조사가 열린 날 기준으로 센다.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT MAX(exmn_ymd) FROM veg_daily_price_raw
            WHERE se_cd='02' AND grd_cd='04' AND mrkt_nm='가락도매'
              AND item_nm IN ('배추','양파','무')""")
        last_data = cur.fetchone()[0]
        cur.execute("""SELECT COUNT(*) FROM ref_calendar
                       WHERE is_survey AND dt > %s AND dt <= CURRENT_DATE""",
                    (last_data,))
        return last_data, cur.fetchone()[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", help="쉼표로 구분. 기본 전체")
    ap.add_argument("--skip", help="건너뛸 단계")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="수집 단계 하나라도 실패하면 중단 (기본은 계속)")
    ap.add_argument("--max-survey-lag", type=int, default=MAX_SURVEY_LAG)
    ap.add_argument("--force-stale", action="store_true",
                    help="앵커가 낡아도 추론한다. 결과를 오늘 값으로 쓰지 말 것")
    a = ap.parse_args()

    want = [s.strip() for s in a.stages.split(",")] if a.stages else list(NAMES)
    skip = {s.strip() for s in a.skip.split(",")} if a.skip else set()
    bad = [s for s in want if s not in NAMES]
    if bad:
        sys.exit("모르는 단계: %s\n  가능: %s" % (bad, ", ".join(NAMES)))
    plan = [s for s in want if s not in skip]

    today = datetime.date.today()
    LOGDIR.mkdir(parents=True, exist_ok=True)
    logpath = LOGDIR / ("batch_%s.log" % today.isoformat())

    print("=" * 70)
    print(" 원가 캣쳐 일별 배치 · %s" % today)
    print("=" * 70)
    for name, desc, cwd, _ in STAGES:
        mark = "▶" if name in plan else "·"
        print("  %s %-18s %s" % (mark, name, desc))
    print("  로그: %s" % logpath)
    if a.dry_run:
        print("\n--dry-run 이므로 실행하지 않았습니다.")
        return

    import psycopg
    conn = psycopg.connect(dsn(), connect_timeout=25)

    # 수집 기간은 DB 최신일에서 자동으로 정한다.
    #   날짜를 하드코딩하지 않는다 — v5 의 '2025-12-31' 하드코딩 때문에
    #   RAW 8개월치가 조용히 버려진 적이 있다 (2026-08-25).
    with conn.cursor() as cur:
        cur.execute('SELECT MAX("tm")::date FROM weather_asos_raw')
        wx_from = cur.fetchone()[0] + datetime.timedelta(days=1)
        cur.execute("SELECT MAX(base_date) FROM daily_volume")
        vol_from = cur.fetchone()[0] - datetime.timedelta(days=5)   # 8일 창이 겹치게
        # 경제변수는 ECOS 수정 후 시계열이라 과거가 정정될 수 있다. 90일 겹쳐 받아
        # 정정을 반영하되, 매번 11년치를 다시 받지는 않는다 (기본값이 2015-01-01).
        #   증분이 전체본과 값이 같은지 확인함(2026-08-25, 91행 불일치 0).
        #   도구가 시작일 이전 데이터를 참조해 전년동월비·직전값 전달을 계산한다.
        cur.execute("SELECT MAX(dt)::date FROM econ_daily_raw")
        e = cur.fetchone()[0]
        econ_from = (e - datetime.timedelta(days=90)) if e else datetime.date(2015, 1, 1)

    dyn = {
        # 수집기가 DB 에 바로 넣는다. CSV 는 만들지 않는다.
        #   CSV 는 타입을 지우고(빈문자열 vs NULL · 실수 vs 정수) 로더가 그걸
        #   손으로 복원해야 한다. 복원 규칙이 갈라지면 조용히 틀린다.
        "collect_weather": [PY, "fetch_asos.py",
                            wx_from.strftime("%Y%m%d"),
                            (today - datetime.timedelta(days=1)).strftime("%Y%m%d"),
                            "--load-db", "--no-csv"],
        "collect_volume": [PY, "농넷에서 일일산출량 적재.py", "run",
                           "--start", vol_from.isoformat(),
                           "--end", today.isoformat(),
                           "--load-db", "--no-csv"],
        # 증분본은 따로 쓴다. 기본 출력(output/economic_variables_daily.csv)은
        # 전 구간본이라 90일치로 덮어쓰면 안 된다.
        "collect_econ": [PY, "fetch_economic_variables.py",
                         "--start-date", econ_from.isoformat(),
                         "--load-db", "--no-csv"],
        "rebuild": None, "predict": None, "shadow": None, "load": None,
        "score": None,
    }
    # 수집 뒤 별도 적재 — 이제 수집기가 직접 넣으므로 비어 있다.
    #   load_to_pg.py · load_daily_volume.py 는 남겨뒀다. 이미 받아둔 CSV 를
    #   넣거나 과거분을 복구할 때 쓴다.
    after = {}

    failed, done = [], []
    rid = run_begin(conn, plan)
    if rid:
        print("  실행 id: %d" % rid)
    seq = 0
    stopped = False
    log = open(logpath, "a", encoding="utf-8")
    log.write("\n\n%s\n배치 시작 %s\n%s\n" % ("=" * 70, datetime.datetime.now(), "=" * 70))

    for name, desc, cwd, cmd in STAGES:
        if name not in plan:
            continue
        print("\n[%s] %s" % (name, desc))
        log.write("\n---- %s ----\n" % name)
        t_stage = time.time()

        if name == "rebuild":
            ok, tail = do_rebuild(conn, log)
        elif name in ("predict", "shadow", "load", "score"):
            ok, tail = do_ml(name, conn, log, a, today)
        elif name == "collect_weather" and wx_from > today - datetime.timedelta(days=1):
            # ASOS 는 전일(D-1)까지만 제공한다. 이미 받아뒀으면 받을 게 없다.
            # fetch_asos.py 는 이 경우 오류로 끝나는데(수동 실행에서는 맞는 동작),
            # 배치에서는 실패가 아니라 "할 일 없음" 이다.
            ok, tail = True, "이미 최신 (DB %s · 제공 한계 %s)" % (
                wx_from - datetime.timedelta(days=1), today - datetime.timedelta(days=1))
        else:
            c = cmd or dyn[name]
            ok, tail = run(c, cwd, log, timeout=3600)
            if ok and name in after:
                steps = after[name]
                steps = steps if isinstance(steps[0], list) else [steps]
                for st in steps:
                    ok, tail = run(st, cwd, log, timeout=1800)
                    if not ok:
                        break

        #   경락가 말고 다른 수집기도 같은 눈으로 본다.
        if ok and name in GAP_CHECKS:
            ok2, gap_msg = check_source_gap(conn, log, today, name)
            if gap_msg:
                print("    " + gap_msg.split(chr(10))[0])
            if not ok2:
                ok = False
                tail = (tail + chr(10) + gap_msg) if tail else gap_msg

        #   수집기가 성공이라 해도 표를 직접 본다 (2026-08-31 사고).
        if ok and name == "collect_auction":
            ok2, gap_msg = check_auction_gap(conn, log, today)
            print("    " + gap_msg.split(chr(10))[0])
            if not ok2:
                ok = False
                tail = (tail + chr(10) + gap_msg) if tail else gap_msg

        print("  %s" % ("성공" if ok else "실패"))
        for line in tail.split("\n"):
            print("    " + line)
        (done if ok else failed).append(name)
        seq += 1
        stage_log(conn, rid, seq, name, ok, time.time() - t_stage, tail)

        if not ok:
            if name.startswith("collect_") and not a.strict:
                print("  → 수집 단계는 계속 진행합니다 (--strict 로 중단 가능)")
                continue
            print("\n중단합니다. 이후 단계는 돌리지 않습니다.")
            stopped = True
            break

    run_end(conn, rid, done, failed, stopped)
    log.close()
    conn.close()
    print("\n" + "=" * 70)
    print(" 성공 %d · 실패 %d" % (len(done), len(failed)))
    if failed:
        print(" 실패: %s" % ", ".join(failed))
        print(" 로그: %s" % logpath)
        notify(failed, rid, logpath)
        call_agent(rid)
        sys.exit(1)
    clear_alert(plan)


# ── 실패 알림 ────────────────────────────────────────────────────────
#   왜 필요한가: 2026-08-27 09:00 배치가 추론에서 멈췄는데 **9시간 동안
#   아무도 몰랐다.** 무인으로 도는 이상 실패를 사람에게 밀어줘야 한다.
#
#   채널이 아직 안 정해져서 세 가지를 다 한다. 하나라도 눈에 띄면 된다.
#     1) 알림 파일 — 항상 남긴다. 대시보드·다른 도구가 읽을 수 있다
#     2) 윈도우 알림 — 설정 없이 바로 뜬다
#     3) 웹훅 — .env 에 NOTIFY_WEBHOOK 이 있을 때만
#
#   알림이 실패해도 배치 결과를 바꾸지 않는다. 알리다 죽으면 본말전도다.
ALERT_FILE = ROOT / "진행기록" / "batch_logs" / "ALERT.txt"


def notify(failed, run_id, logpath):
    when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = (chr(10).join([
        "[원가캣쳐 배치 실패] " + when,
        "실패 단계: " + ", ".join(failed),
        "run_id: %s" % run_id,
        "로그: %s" % logpath,
    ]))
    try:
        ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
        ALERT_FILE.write_text(msg + chr(10), encoding="utf-8")
    except Exception:                                        # noqa: BLE001
        pass
    try:
        ps = ("[reflection.assembly]::LoadWithPartialName('System.Windows.Forms')|Out-Null;"
              "$n=New-Object System.Windows.Forms.NotifyIcon;"
              "$n.Icon=[System.Drawing.SystemIcons]::Error;$n.Visible=$true;"
              "$n.ShowBalloonTip(20000,'원가캣쳐 배치 실패','%s','Error');"
              "Start-Sleep -Seconds 12" % ", ".join(failed))
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       timeout=40, capture_output=True)
    except Exception:                                        # noqa: BLE001
        pass
    url = os.environ.get("NOTIFY_WEBHOOK", "").strip()
    if url:
        try:
            import json as _json
            import urllib.request as _u
            req = _u.Request(url, data=_json.dumps({"text": msg}).encode("utf-8"),
                             headers={"Content-Type": "application/json"})
            _u.urlopen(req, timeout=15)
        except Exception:                                    # noqa: BLE001
            pass
    print(" 알림: %s" % ALERT_FILE)


def call_agent(run_id):
    """실패했을 때 조사 도우미를 부른다 (2026-08-31 추가).

    왜 필요한가: 08-29·08-30·08-31 아침에 배치가 연속으로 실패했는데
    **사흘 동안 아무도 몰랐다.** 알림 파일은 떴지만 열어보지 않았다.
    원인은 오류 문구 한 줄에 다 있었는데, 그걸 읽고 코드까지 이어붙이는
    데 사람이 30분을 썼다.

    도우미가 그 조사를 대신하고 **결과를 ALERT.txt 에 덧붙인다.**
    사람이 파일 하나만 열면 무슨 일인지 알 수 있게 하려는 것이다.

    ★ notify() 와 같은 원칙: **도우미가 실패해도 배치 결과를 바꾸지 않는다.**
      알리다 죽으면 본말전도다. 그래서 통째로 감싸고 시간 제한을 둔다.
      또 배치는 이미 실패로 끝나는 중이므로 종료 코드도 건드리지 않는다.
    """
    script = ROOT / "agent" / "batch_agent.py"
    if not script.exists():
        return
    try:
        print(" 조사 도우미 실행 중 …")
        r = subprocess.run(
            [PY, str(script), "--run-id", str(run_id), "--append-alert"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        out = (r.stdout or "").strip()
        if out:
            print(out[-3000:])
    except subprocess.TimeoutExpired:
        print(" [주의] 조사 도우미가 5분을 넘겨 중단했습니다.")
    except Exception as error:                               # noqa: BLE001
        print(" [주의] 조사 도우미 실행 실패: %s" % error)


def clear_alert(plan):
    """성공했으면 지난 경보를 지운다.

    왜 필요한가: 경보를 **만드는 코드만 있고 지우는 코드가 없었다**
    (2026-08-27 발견). 한 번 실패하면 그 뒤로 계속 성공해도 파일이 남아
    "매일 실패 중" 으로 보인다. 경보가 상시 켜져 있으면 사람이 무시하게 되고,
    그러면 진짜 실패도 같이 묻힌다.

    ★ `push` 를 돈 실행에서만 지운다. 경보가 답하는 질문은 "오늘 예측이
      만들어져 전달됐나" 이므로, 그 답을 낼 수 있는 실행만 경보를 내릴
      자격이 있다. `--stages collect_auction` 처럼 일부만 돌린 실행이
      전체 실패를 덮으면 안 된다.
    """
    if "push" not in plan:
        if ALERT_FILE.exists():
            print(" 경보 유지: %s (push 를 돌지 않아 판단 보류)" % ALERT_FILE)
        return
    if not ALERT_FILE.exists():
        return
    try:
        ALERT_FILE.unlink()
        print(" 경보 해제: 지난 실패 알림을 지웠습니다")
    except Exception:                                        # noqa: BLE001
        pass


def do_rebuild(conn, log):
    """v5 를 트랜잭션 안에서 돌리고, 성공했을 때만 커밋한다."""
    sql = (ROOT / "SQL" / "DBEAVER_run_v5.sql").read_text(encoding="utf-8")
    notices = []
    conn.add_notice_handler(lambda d: notices.append(d.message_primary))
    t0 = time.time()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            while cur.nextset():
                pass
        conn.commit()
    except Exception as e:                                   # noqa: BLE001
        conn.rollback()
        log.write("v5 실패: %s\n" % e)
        return False, "v5 실패 — 롤백했습니다: %s" % str(e)[:200]
    keep = [m for m in notices
            if "already exists" not in m and "does not exist" not in m]
    for m in keep:
        log.write("  " + m + "\n")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), MAX(base_dt) FROM crop_price_train")
        n, mx = cur.fetchone()
        cur.execute("SELECT COUNT(*), MAX(base_dt) FROM predict_input")
        pn, pmx = cur.fetchone()
    return True, ("crop_price_train %s행 · ~%s\npredict_input %s행 · ~%s\n  (%.0f초)"
                  % (format(n, ","), mx, format(pn, ","), pmx, time.time() - t0))


def do_ml(name, conn, log, a, today):
    """추론·적재·채점. predict 전에 신선도를 재고, 낡으면 멈춘다."""
    out = ROOT / "진행기록" / "batch_logs"
    if name == "predict":
        last, lag = survey_lag(conn)
        msg = "앵커 최신 조사일 %s · 조사일 기준 %d일 밀림" % (last, lag)
        log.write(msg + "\n")
        if lag > a.max_survey_lag and not a.force_stale:
            return False, (msg + "\n임계 %d일을 넘어 추론하지 않습니다.\n"
                           "  수집을 먼저 돌리세요. 그래도 내려면 --force-stale"
                           % a.max_survey_lag)
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(base_dt) FROM predict_input")
            base = cur.fetchone()[0]
        tails = []
        for kind, mdir in MODELS.items():
            csv = out / ("pi_%s.csv" % kind)
            ok, t = run([PY, "export_predict_input.py", "--base-dt", str(base),
                         "--out", str(csv)], KIT, log, timeout=600)
            if not ok:
                return False, "predict_input 내보내기 실패\n" + t
            ok, t = run([PY, "predict.py", str(csv), "--model-dir", mdir,
                         "--model-ver", mdir,
                         "--out", str(out / ("pred_%s.csv" % kind))],
                        KIT, log, timeout=900)
            if not ok:
                return False, "%s 추론 실패\n%s" % (kind, t)
            tails.append("%s ok" % kind)
        return True, msg + "\n기준일 %s · " % base + " · ".join(tails)

    if name == "shadow":
        # ── 그림자 실행 ────────────────────────────────────────────
        #   ★ 여기서 실패해도 배치는 계속된다. 알리다가 죽으면 본말전도다.
        #     그림자는 "확인용" 이지 "결과물" 이 아니다.
        import csv as _csv
        try:
            import pandas as _pd
        except Exception as e:                                # noqa: BLE001
            return True, "건너뜀 (pandas 없음: %s)" % e
        rows, notes = [], []
        for kind, mdir in SHADOW.items():
            if not (KIT / mdir).exists():
                notes.append("%s 번들 없음" % kind)
                continue
            src = out / ("pi_%s.csv" % kind)
            if not src.exists():
                notes.append("%s 입력 없음" % kind)
                continue
            dst = out / ("shadow_%s.csv" % kind)
            ok, t = run([PY, "predict.py", str(src), "--model-dir", mdir,
                         "--model-ver", mdir, "--out", str(dst)],
                        KIT, log, timeout=900)
            if not ok:
                notes.append("%s 추론 실패" % kind)
                continue
            base_f = out / ("pred_%s.csv" % kind)
            if not base_f.exists():
                notes.append("%s 운영 예측 없음" % kind)
                continue
            a = _pd.read_csv(base_f, encoding="utf-8-sig")
            b = _pd.read_csv(dst, encoding="utf-8-sig")
            k = ["base_dt", "item_nm", "lead_biz_d"]
            m = a.merge(b, on=k, suffixes=("_o", "_q"))
            if m.empty:
                notes.append("%s 맞춘 행 0" % kind)
                continue
            #   ★ 점 예측이 다르면 그건 사고다. 구간만 바뀌어야 한다.
            d = (m.pred_prc_o - m.pred_prc_q).abs()
            diff = int((d > 1e-6).sum())
            for it, g in m.groupby("item_nm"):
                wo = ((g.pred_hi_o - g.pred_lo_o) / g.pred_prc_o).mean()
                wq = ((g.pred_hi_q - g.pred_lo_q) / g.pred_prc_q).mean()
                rows.append(dict(run_dt=today.isoformat(),
                                 base_dt=str(g.base_dt.iloc[0]),
                                 target=kind, item_nm=it, n=len(g),
                                 pred_diff_rows=diff,
                                 width_ops=round(float(wo), 4),
                                 width_q=round(float(wq), 4)))
            notes.append("%s 비교 %d행 · 점예측 차이 %d행" % (kind, len(m), diff))
        if rows:
            SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
            new = not SHADOW_LOG.exists()
            with open(SHADOW_LOG, "a", encoding="utf-8-sig", newline="") as f:
                w = _csv.DictWriter(f, fieldnames=list(rows[0]))
                if new:
                    w.writeheader()
                w.writerows(rows)
            bad = sum(r["pred_diff_rows"] for r in rows)
            if bad:
                #   실패로 만들지는 않는다. 다만 눈에 띄게 남긴다.
                notes.append("[주의] 점 예측이 달라진 행이 있습니다 (%d)" % bad)
        return True, " · ".join(notes) if notes else "비교할 것이 없었습니다"

    if name == "load":
        files = [str(out / ("pred_%s.csv" % k)) for k in MODELS]
        return run([PY, "load_predictions.py"] + files, KIT, log, timeout=900)

    return run([PY, "score_predictions.py"], KIT, log, timeout=1800)


if __name__ == "__main__":
    main()
