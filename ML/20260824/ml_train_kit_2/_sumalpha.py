# -*- coding: utf-8 -*-
import io, re, os, glob
LBL = {'auc': '경락가', 'whsl': '중도매가', 'rtl': '소매가'}
R = {}
for p in sorted(glob.glob('results/alpha_20260828/*.txt')):
    b = os.path.basename(p).replace('.txt', '')
    tgt, fold, al = b.split('_')
    fold = fold.replace('fold', ''); al = '1.0' if al == 'a10' else '0.6'
    s = io.open(p, encoding='utf-8').read()
    m = re.search(r'앙상블 ([\d.]+)\s+baseline 대비 ([+-][\d.]+)%', s)
    sd = re.search(r'시드별 [\d.]+ ± ([\d.]+)', s)
    bl = re.search(r'\[통합\] (\S+) ([\d.]+)', s)
    err = {}
    blk = re.search(r'\[검증 실제 가격 대비 오차\](.*?)(?:\[검증 리드|\Z)', s, re.S)
    if blk:
        for line in blk.group(1).splitlines():
            f = line.split()
            if len(f) >= 4 and f[0] in ('무', '배추', '양파', '전체'):
                err[f[0]] = (f[1], f[2], f[3])
    R[(tgt, fold, al)] = dict(w=m.group(1) if m else '?', i=m.group(2) if m else '?',
                              sd=sd.group(1) if sd else '?',
                              best=bl.group(1) if bl else '?', err=err)

print('[개선율 — 최강 baseline 대비]')
print('%-9s %-6s %-11s %-11s %-9s' % ('타겟', '폴드', 'α=1.0(현행)', 'α=0.6', '변화'))
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        a1 = R.get((t, f, '1.0')); a6 = R.get((t, f, '0.6'))
        if not (a1 and a6):
            continue
        d = float(a6['i']) - float(a1['i'])
        print('%-9s %-6s %-11s %-11s %+8.1f%%p' % (
            LBL[t], f, a1['i'] + '%', a6['i'] + '%', d))
print()
print('[전체 오차율 — 실제 가격 대비]')
print('%-9s %-6s %-12s %-12s' % ('타겟', '폴드', 'α=1.0', 'α=0.6'))
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        a1 = R.get((t, f, '1.0')); a6 = R.get((t, f, '0.6'))
        if not (a1 and a6):
            continue
        e1 = a1['err'].get('전체', ('', '', '?'))[2]
        e6 = a6['err'].get('전체', ('', '', '?'))[2]
        print('%-9s %-6s %-12s %-12s' % (LBL[t], f, e1, e6))
