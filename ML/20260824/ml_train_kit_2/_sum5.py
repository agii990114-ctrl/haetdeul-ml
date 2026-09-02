# -*- coding: utf-8 -*-
import io, re, os, glob
LBL = {'auc': '경락가', 'whsl': '중도매가', 'rtl': '소매가'}
R = {}
for p in sorted(glob.glob('results/alpha5_20260828/*.txt')):
    tgt, fold, al = os.path.basename(p).replace('.txt', '').split('_')
    fold = fold.replace('fold', '')
    al = {'a10': '1.0', 'a08': '0.8', 'a06': '0.6', 'a04': '0.4', 'a02': '0.2'}[al]
    s = io.open(p, encoding='utf-8').read()
    m = re.search(r'앙상블 ([\d.]+)\s+baseline 대비 ([+-]?[\d.]+)%', s)
    bl = re.search(r'\[통합\] (\S+) ([\d.]+)', s)
    sd = re.search(r'시드별 [\d.]+ ± ([\d.]+)', s)
    R[(tgt, fold, al)] = dict(w=m.group(1) if m else '?', i=m.group(2) if m else '?',
                              best=bl.group(1) if bl else '?', sd=sd.group(1) if sd else '?')

ALS = ['1.0', '0.8', '0.6', '0.4', '0.2']
print('[모델 WMAPE — 낮을수록 좋음]')
print('%-9s %-5s ' % ('타겟', '폴드') + ' '.join('α=%-7s' % a for a in ALS))
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        cells = [R.get((t, f, a), {}).get('w', '?') for a in ALS]
        print('%-9s %-5s ' % (LBL[t], f) + ' '.join('%-9s' % c for c in cells))
print()
print('[baseline 대비 개선율 — baseline 후보 8개 중 최강]')
print('%-9s %-5s ' % ('타겟', '폴드') + ' '.join('α=%-7s' % a for a in ALS))
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        cells = [R.get((t, f, a), {}).get('i', '?') + '%' for a in ALS]
        print('%-9s %-5s ' % (LBL[t], f) + ' '.join('%-9s' % c for c in cells))
print()
print('[그때의 최강 baseline]')
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        cells = [R.get((t, f, a), {}).get('best', '?') for a in ALS]
        print('%-9s %-5s ' % (LBL[t], f) + ' '.join('%-13s' % c for c in cells))
