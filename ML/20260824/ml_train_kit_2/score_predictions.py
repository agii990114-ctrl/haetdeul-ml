# -*- coding: utf-8 -*-
"""
예측 채점 — prediction_log 에 실제값 채우기
============================================
대상일이 지나고 실제 가격이 들어오면 `actual_prc` · `abs_pct_err` · `scored_at`
을 채운다. **이게 없으면 모델이 실제로 맞았는지 영영 모른다.**

    python score_predictions.py --check      # 채점 대상만 보여준다
    python score_predictions.py              # 채점
    python score_predictions.py --rescore    # 이미 채점된 것도 다시 (원천 정정 반영)

실제값을 어디서 가져오나
------------------------
타겟마다 원천과 필터가 다르다. **학습 타겟과 정확히 같은 정의**를 써야 한다.
다르면 모델을 실제보다 나쁘거나 좋게 채점하게 된다.

    auc   auction_prices_daily · 서울가락(110001) · 특등급(11) · 평균 경락가
    whsl  veg_daily_price_raw  · se_cd=02 · grd_cd=04 · 가락도매 · 원/kg 정규화
    rtl   veg_daily_price_raw  · se_cd=01 · grd_cd=04 · 서울(1101) · 원/단위

`whsl`·`rtl` 의 단위 정규화(`prc / unit_sz`)는 v5 STEP 1 과 같은 식이다.
한쪽만 바꾸면 조용히 어긋나므로, 아래 SQL 을 고칠 때 v5 도 함께 볼 것.

채점하지 않는 것
----------------
· 대상일이 아직 오지 않은 예측 (target_dt > 오늘)
· 실제 가격이 아직 안 들어온 대상일 — 조사·공개 지연이 있어 정상이다.
  못 찾은 건수를 보고하되 0 으로 채우지 않는다. **결측과 0 은 다르다.**
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[3]

# 타겟별 실제값 — 학습 타겟과 같은 정의여야 한다 (v5 STEP 1·6 참조)
#
# ★★ 2026-08-31 수정 — 경락가 채점이 **틀린 정답으로 채점하고 있었다.**
#
#   08-27 에 타겟(v5 tmp_auc)은 규격을 고정했는데, **채점은 안 고쳤다.**
#   위 주석에 "학습 타겟과 같은 정의여야 한다" 고 적어놓고 어긋나 있었다.
#
#   틀린 점이 둘이었다.
#     ① 규격을 안 걸었다 — 15개 포장이 한 평균에 섞였다
#     ② AVG(단가) 로 뭉갰다 — 물량가중이 아니라 행 단순평균이라,
#        1kg 소포장 한 건이 79% 물량의 10kg 그물망과 같은 무게로 들어갔다
#
#   실측 피해 (정답표 crop_price_train 과 대조):
#       auc    34,905행 중 25,866행 불일치 (74.1%) · 평균 8.2% 어긋남
#       whsl   불일치 0
#       rtl    불일치 0
#     품목별  배추 20.2% · 양파 4.0% · 무 0.6% 어긋남
#     최악 사례  무 2026-01-09  정답 521원 → 채점값 2,545원
#
#   그래서 2026-08-31 이전에 나온 **경락가 실전 채점 수치는 전부 무효**다.
#   중도매가·소매가는 영향이 없다.
#
#   아래는 v5 STEP 5 의 tmp_auc 내부 쿼리를 그대로 옮긴 것이다.
#   **한쪽만 고치면 또 갈라진다.** v5 를 고치면 여기도 같이 고칠 것.
ACTUAL_SQL = {
    "auc": """
        SELECT auction_date AS dt, item_name AS item_nm,
               (SUM(trade_amount_krw) / NULLIF(SUM(trade_volume_kg), 0))::NUMERIC(15,3) AS prc
        FROM auction_prices_daily
        WHERE wholesale_market_code = '110001'   -- 서울가락
          AND grade_code            = '11'       -- 특등급
          AND avg_auction_price_krw_per_kg > 0
          AND trade_volume_kg > 0
          AND (   (item_name = '배추' AND package_name IN ('그물망', '파렛트'))
               OR (item_name = '무'   AND package_name IN ('상자',   '파렛트'))
               OR (item_name = '양파' AND package_name IN ('그물망', '파렛트'))
               OR (item_name NOT IN ('배추', '무', '양파')))
          AND (   (item_name = '배추' AND unit_weight_kg = 10)
               OR (item_name = '무' AND (
                       (auction_date <  DATE '2018-01-01' AND unit_weight_kg = 18)
                    OR (auction_date >= DATE '2018-01-01' AND unit_weight_kg = 20)))
               OR (item_name = '양파' AND unit_weight_kg = 15)
               OR (item_name NOT IN ('배추', '무', '양파')))
        GROUP BY 1, 2""",
    "whsl": """
        SELECT exmn_ymd AS dt, item_nm,
               AVG(exmn_dd_prc / NULLIF(unit_sz, 0))::NUMERIC(15,3) AS prc
        FROM veg_daily_price_raw
        WHERE se_cd = '02' AND grd_cd = '04' AND mrkt_nm = '가락도매'
          AND exmn_dd_prc IS NOT NULL AND unit_sz > 0
        GROUP BY 1, 2""",
    "rtl": """
        SELECT exmn_ymd AS dt, item_nm,
               AVG(exmn_dd_prc / NULLIF(unit_sz, 0))::NUMERIC(15,3) AS prc
        FROM veg_daily_price_raw
        WHERE se_cd = '01' AND grd_cd = '04' AND sgg_cd = '1101'
          AND exmn_dd_prc IS NOT NULL AND unit_sz > 0
        GROUP BY 1, 2""",
}


def dsn():
    p = ROOT / ".env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8-sig").splitlines():
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="채점 대상만 보고 쓰지 않는다")
    ap.add_argument("--rescore", action="store_true",
                    help="이미 채점된 행도 다시 채점 (원천이 정정됐을 때)")
    ap.add_argument("--kinds", nargs="+", default=["auc", "whsl", "rtl"])
    ap.add_argument("--include-dummy", action="store_true",
                    help="model_ver 이 dummy 로 시작하는 행도 채점한다 (기본 제외)")
    a = ap.parse_args()

    # 더미는 다른 파트 연동용으로 만든 가짜 예측이다. 실제값을 채우면
    # 지어낸 pred_prc 와 진짜 가격을 비교한 MAPE 가 리포트에 섞인다.
    #   LIKE 의 % 는 psycopg 플레이스홀더와 충돌한다. left() 로 같은 일을 한다.
    skip_dummy = "" if a.include_dummy else "AND left(p.model_ver, 5) <> 'dummy'"

    conn = psycopg.connect(dsn(), connect_timeout=25)
    total = 0
    with conn.cursor() as cur:
        cur.execute("""SELECT COUNT(*),
                              COUNT(*) FILTER (WHERE actual_prc IS NOT NULL),
                              COUNT(*) FILTER (WHERE target_dt > CURRENT_DATE)
                       FROM prediction_log""")
        n, scored, future = cur.fetchone()
        print("[현황] prediction_log %d행 · 채점됨 %d · 대상일 미도래 %d"
              % (n, scored, future))

        for kind in a.kinds:
            if kind not in ACTUAL_SQL:
                print("  [건너뜀] 모르는 타겟: %s" % kind)
                continue
            where_scored = ("" if a.rescore else "AND p.actual_prc IS NULL") + " " + skip_dummy

            cur.execute("""
                SELECT COUNT(*) FROM prediction_log p
                WHERE p.target_kind = %%s AND p.target_dt <= CURRENT_DATE %s
            """ % where_scored, (kind,))
            cand = cur.fetchone()[0]

            # 실제값이 실제로 있는 것만 센다. 없는 건 조사·공개 지연이라 정상이다.
            sql_cnt = """
                WITH act AS (%s)
                SELECT COUNT(*) FROM prediction_log p
                JOIN act a ON a.dt = p.target_dt AND a.item_nm = p.item_nm
                WHERE p.target_kind = %%s AND p.target_dt <= CURRENT_DATE %s
                  AND a.prc IS NOT NULL AND a.prc > 0
            """ % (ACTUAL_SQL[kind], where_scored)
            cur.execute(sql_cnt, (kind,))
            hit = cur.fetchone()[0]
            print("  %-5s 채점 대상 %4d · 실제값 있음 %4d · 대기 %4d"
                  % (kind, cand, hit, cand - hit))

            if a.check or hit == 0:
                continue

            sql_upd = """
                WITH act AS (%s)
                UPDATE prediction_log p
                   SET actual_prc  = a.prc,
                       abs_pct_err = ROUND(ABS(p.pred_prc - a.prc)
                                           / NULLIF(a.prc, 0) * 100, 4),
                       scored_at   = now()
                  FROM act a
                 WHERE a.dt = p.target_dt AND a.item_nm = p.item_nm
                   AND p.target_kind = %%s AND p.target_dt <= CURRENT_DATE %s
                   AND a.prc IS NOT NULL AND a.prc > 0
            """ % (ACTUAL_SQL[kind], where_scored)
            cur.execute(sql_upd, (kind,))
            total += cur.rowcount
            print("        → %d행 채점" % cur.rowcount)

        if a.check:
            print("\n--check 이므로 쓰지 않았습니다.")
            conn.close()
            return
        conn.commit()

        # ── 채점 결과 ──────────────────────────────────────────
        #   게이트된 행은 모델이 아니라 앵커의 오차다. 섞으면 모델 성능이 왜곡되므로
        #   나눠서 본다. baseline 대비 개선율이 실제 성과다.
        print("\n[채점 결과] 모델이 실제로 쓰인 행만 (gated 제외)")
        cur.execute("""
            SELECT target_kind, item_nm,
                   COUNT(*),
                   ROUND(AVG(abs_pct_err), 2)                       AS 모델_MAPE,
                   ROUND(AVG(ABS(anchor_prc - actual_prc)
                             / NULLIF(actual_prc,0) * 100), 2)      AS 앵커_MAPE,
                   ROUND(AVG(CASE WHEN actual_prc BETWEEN pred_lo AND pred_hi
                                  THEN 1 ELSE 0 END) * 100, 1)      AS 구간적중_pct
            FROM prediction_log
            WHERE actual_prc IS NOT NULL AND NOT gated
              AND left(model_ver, 5) <> 'dummy'
            GROUP BY 1, 2 ORDER BY 1, 2""")
        rows = cur.fetchall()
        if rows:
            print("  %-5s %-5s %6s %10s %10s %10s %9s"
                  % ("타겟", "품목", "행수", "모델MAPE", "앵커MAPE", "개선율", "구간적중"))
            for k, it, c, m, an, band in rows:
                imp = (1 - float(m) / float(an)) * 100 if an else float("nan")
                print("  %-5s %-5s %6d %9s%% %9s%% %+9.1f%% %8s%%"
                      % (k, it, c, m, an, imp, band))
            print("\n  개선율이 음수면 그 조합은 앵커가 낫습니다 — "
                  "ref_prediction_quality 를 갱신하세요.")
        else:
            print("  (아직 없음)")
    conn.close()
    if total:
        print("\n총 %d행 채점" % total)


if __name__ == "__main__":
    main()
