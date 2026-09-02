# -*- coding: utf-8 -*-
import io, re, os, glob
LBL = {'auc': '경락가', 'whsl': '중도매가', 'rtl': '소매가'}
res = {}
for p in sorted(glob.glob('results/remeasure_20260828b/*.txt')):
    tgt, fold = os.path.basename(p).replace('.txt', '').split('_fold')
    s = io.open(p, encoding='utf-8').read()
    ens = re.search(r'앙상블 ([\d.]+)', s)
    block = re.search(r'\[검증 품목별 성능\](.*?)(?:\[검증 리드)', s, re.S)
    items = {}
    if block:
        for line in block.group(1).strip().splitlines():
            f = line.split()
            if len(f) >= 3 and f[0] in ('무', '배추', '양파'):
                items[f[0]] = (float(f[1]), float(f[2]))   # 모델, baseline
    res[(tgt, fold)] = (float(ens.group(1)) if ens else None, items)

print('[통합 오차율 — 검증 구간]')
print('%-9s %-14s %-14s' % ('가격', '시험2023', '시험2022'))
for t in ['auc', 'whsl', 'rtl']:
    a = res.get((t, 'A'), (None, {}))[0]
    b = res.get((t, 'B'), (None, {}))[0]
    print('%-9s %-14s %-14s' % (LBL[t], f'{a*100:.1f}%' if a else '-', f'{b*100:.1f}%' if b else '-'))
print()
print('[품목별 오차율 — 모델 / 게으른답]')
print('%-9s %-5s %-17s %-17s %-17s' % ('가격', '시험', '배추', '무', '양파'))
for t in ['auc', 'whsl', 'rtl']:
    for f, yr in [('A', '2023'), ('B', '2022')]:
        it = res.get((t, f), (None, {}))[1]
        def g(k):
            v = it.get(k)
            return f'{v[0]*100:.1f}% / {v[1]*100:.1f}%' if v else '-'
        print('%-9s %-5s %-17s %-17s %-17s' % (LBL[t], yr, g('배추'), g('무'), g('양파')))
