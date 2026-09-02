# -*- coding: utf-8 -*-
import io, re, os, glob
LBL = {'auc': '경락가', 'whsl': '중도매가', 'rtl': '소매가'}
res = {}
for p in sorted(glob.glob('results/remeasure_20260828b/*.txt')):
    tag = os.path.basename(p).replace('.txt', '')
    tgt, fold = tag.split('_fold')
    s = io.open(p, encoding='utf-8').read()
    m = re.search(r'앙상블 ([\d.]+)\s+baseline 대비 ([+-][\d.]+)%', s)
    sd = re.search(r'시드별 ([\d.]+) ± ([\d.]+)', s)
    block = re.search(r'\[검증 품목별 성능\](.*?)(?:\[검증 리드)', s, re.S)
    items = {}
    if block:
        for line in block.group(1).strip().splitlines():
            f = line.split()
            if len(f) >= 4 and f[0] in ('무', '배추', '양파'):
                items[f[0]] = f[3]
    bl = re.search(r'\[통합\] (\S+) ([\d.]+)', s)
    res[(tgt, fold)] = dict(w=m.group(1) if m else '?', i=m.group(2) if m else '?',
                            sd=sd.group(2) if sd else '?', items=items,
                            best=bl.group(1) if bl else '?')
print('%-9s %-4s %-10s %-13s %-9s %s' % ('타겟', '폴드', '모델WMAPE', '최강baseline', '개선율', '시드편차'))
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        r = res.get((t, f))
        if r:
            print('%-9s %-4s %-10s %-13s %-9s ±%s' % (LBL[t], f, r['w'], r['best'], r['i'] + '%', r['sd']))
print()
print('[품목별 개선율]')
print('%-9s %-4s %-9s %-9s %-9s' % ('타겟', '폴드', '배추', '무', '양파'))
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        r = res.get((t, f))
        if not r:
            continue
        g = lambda k: r['items'].get(k, '-')
        print('%-9s %-4s %-9s %-9s %-9s' % (LBL[t], f, g('배추'), g('무'), g('양파')))
