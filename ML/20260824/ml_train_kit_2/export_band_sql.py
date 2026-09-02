# -*- coding: utf-8 -*-
"""
예측 구간(밴드) → SQL 내보내기
==============================
모델 번들의 meta.json 에 들어 있는 경험적 밴드를 `ref_prediction_band`
테이블 적재용 SQL 로 만든다.

    python export_band_sql.py model_auc model_whsl model_rtl \
        --out ../../../SQL/27_ref_prediction_band.sql

밴드가 무엇인가
    검증 구간에서 잰 actual / pred 비율의 분위수다.
    q10 ~ q90 이므로 "그 조합에서 10건 중 8건이 이 범위 안에 들어왔다" 는 뜻이다.

    시드 편차(seed_spread)는 밴드로 쓰지 않는다. 시드끼리 얼마나 다르게
    답하느냐일 뿐이라 실제 오차와 자릿수가 다르다.
        실측  시드편차 1.6~1.8%  ·  실제 WMAPE 10~17%
    신뢰구간처럼 쓰면 불확실성을 10배 가까이 과소평가한다.

갱신
    모델을 재학습하면 이 파일도 다시 만들어야 한다. 밴드는 그 모델의
    검증 성능에서 나온 값이므로 모델과 짝이다.
"""
import argparse
import json
import os

KIND_LABEL = {"auc": "경락가", "whsl": "중도매가", "rtl": "소매가"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dirs", nargs="+")
    ap.add_argument("--out", default="ref_prediction_band.sql")
    a = ap.parse_args()

    rows = []
    heads = []
    for d in a.model_dirs:
        mp = os.path.join(d, "meta.json")
        if not os.path.exists(mp):
            raise SystemExit("meta.json 이 없습니다: %s" % mp)
        with open(mp, encoding="utf-8") as f:
            meta = json.load(f)
        band = meta.get("band") or {}
        if not band:
            raise SystemExit("%s 에 밴드가 없습니다. train.py 를 다시 돌리세요." % d)
        kind = meta["target"]
        heads.append("--   %-5s %-8s 조합 %d · 검증 WMAPE %.4f · %s"
                     % (kind, KIND_LABEL.get(kind, ""), len(band),
                        meta.get("valid_wmape_gated", meta.get("valid_wmape", 0)),
                        os.path.basename(os.path.abspath(d))))
        for key, v in sorted(band.items()):
            item, lead = key.rsplit("|", 1)
            rows.append((kind, item, int(lead), v[0], v[1], v[2]))

    rows.sort(key=lambda r: (r[0], r[1], r[2]))

    out = []
    out.append("-- =====================================================================")
    out.append("-- 27_ref_prediction_band.sql — 예측 구간(밴드)")
    out.append("-- =====================================================================")
    out.append("--   ML/20260824/ml_train_kit_2/export_band_sql.py 가 생성한다.")
    out.append("--   손으로 고치지 말고 모델 재학습 후 다시 생성할 것.")
    out.append("--")
    out.append("--   내용: 검증 구간에서 잰 actual / pred 비율의 q10 · q50 · q90")
    out.append("--         품목 × 리드타임 × 타겟별. 10건 중 8건이 q10~q90 안에 든다.")
    out.append("--")
    out.append("--   pred_lo = pred_prc * ratio_q10")
    out.append("--   pred_hi = pred_prc * ratio_q90")
    out.append("--")
    out.append("--   ※ 시드 편차(seed_spread)를 구간으로 쓰지 말 것.")
    out.append("--     실측 시드편차 1.6~1.8% 대 실제 WMAPE 10~17% 로 자릿수가 다르다.")
    out.append("--")
    out.extend(heads)
    out.append("-- =====================================================================")
    out.append("")
    out.append("DROP TABLE IF EXISTS ref_prediction_band;")
    out.append("")
    out.append("CREATE TABLE ref_prediction_band (")
    out.append("    target_kind varchar(4)   NOT NULL,")
    out.append("    item_nm     varchar(20)  NOT NULL,")
    out.append("    lead_biz_d  smallint     NOT NULL,")
    out.append("    ratio_q10   numeric(8,4) NOT NULL,   -- actual/pred 10분위")
    out.append("    ratio_q50   numeric(8,4) NOT NULL,")
    out.append("    ratio_q90   numeric(8,4) NOT NULL,   -- actual/pred 90분위")
    out.append("    PRIMARY KEY (target_kind, item_nm, lead_biz_d)")
    out.append(");")
    out.append("")
    out.append("COMMENT ON TABLE ref_prediction_band IS")
    out.append("  '검증 구간 실측 예측구간. pred_lo=pred*ratio_q10, pred_hi=pred*ratio_q90';")
    out.append("")
    out.append("INSERT INTO ref_prediction_band"
               " (target_kind, item_nm, lead_biz_d, ratio_q10, ratio_q50, ratio_q90) VALUES")
    vals = ["  ('%s', '%s', %d, %.4f, %.4f, %.4f)" % r for r in rows]
    out.append(",\n".join(vals) + ";")
    out.append("")
    out.append("-- 확인: 리드타임이 길수록 폭이 넓어져야 정상")
    out.append("SELECT target_kind, lead_biz_d,")
    out.append("       ROUND(AVG(ratio_q90 - ratio_q10) * 100, 1) AS \"폭%\"")
    out.append("  FROM ref_prediction_band GROUP BY 1,2 ORDER BY 1,2;")
    out.append("")

    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("저장: %s  (%d행 · 타겟 %d개)" % (a.out, len(rows), len(a.model_dirs)))
    for h in heads:
        print(h[2:])


if __name__ == "__main__":
    main()
