# -*- coding: utf-8 -*-
"""백필 예측을 실제값과 대조한다. 2025-12-31 기준일은 이미 지난 날이라 채점이 가능하다."""
import csv, io, psycopg
url = [l.split('=', 1)[1].strip() for l in io.open('../../../.env', encoding='utf-8', errors='ignore')
       if l.startswith('DATABASE_URL')][0]
TCOL = {'auc': 'target_auc_prc', 'whsl': 'target_whsl_prc', 'rtl': 'target_rtl_prc'}
LBL = {'auc': '경락가', 'whsl': '중도매가', 'rtl': '소매가'}
with psycopg.connect(url) as c:
    print('%-9s %-5s %8s %8s %8s %8s' % ('가격', '품목', '행수', '평균오차', '구간적중', '게이트'))
    for t in ['auc', 'whsl', 'rtl']:
        act = {(r[0], r[1]): float(r[2]) for r in c.execute(
            f"SELECT item_nm, lead_biz_d, {TCOL[t]} FROM crop_price_train "
            f"WHERE base_dt=DATE '2025-12-31' AND {TCOL[t]} IS NOT NULL")}
        rows = list(csv.DictReader(io.open(f'bf_{t}.csv', encoding='utf-8')))
        agg = {}
        for r in rows:
            k = (r['item_nm'], int(r['lead_biz_d']))
            a = act.get(k)
            if a is None:
                continue
            p, lo, hi = float(r['pred_prc']), float(r['pred_lo']), float(r['pred_hi'])
            d = agg.setdefault(r['item_nm'], [0, 0.0, 0, 0])
            d[0] += 1
            d[1] += abs(p - a) / a
            d[2] += 1 if lo <= a <= hi else 0
            d[3] += 1 if r.get('gated', '').lower() in ('true', 't', '1') else 0
        for it in sorted(agg):
            n, e, hit, g = agg[it]
            print('%-9s %-5s %8d %7.1f%% %7.1f%% %7d' % (LBL[t], it, n, e / n * 100, hit / n * 100, g))
