# -*- coding: utf-8 -*-
import io, re, os, glob
LBL = {'auc': '경락가', 'whsl': '중도매가', 'rtl': '소매가'}
E = {}
for p in sorted(glob.glob('results/alpha_20260828/*.txt')):
    tgt, fold, al = os.path.basename(p).replace('.txt', '').split('_')
    fold = fold.replace('fold', ''); al = '1.0' if al == 'a10' else '0.6'
    s = io.open(p, encoding='utf-8').read()
    blk = re.search(r'\[검증 실제 가격 대비 오차\](.*?)(?:\[검증 리드)', s, re.S)
    d = {}
    if blk:
        for line in blk.group(1).splitlines():
            f = line.split()
            if len(f) >= 4 and f[0] in ('무', '배추', '양파', '전체'):
                d[f[0]] = f[3]           # 오차율
    E[(tgt, fold, al)] = d

print('[실제 가격 대비 오차율 — α=1.0 → α=0.6]')
print('%-9s %-4s %-16s %-16s %-16s %-16s' % ('타겟', '폴드', '배추', '무', '양파', '전체'))
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        a1, a6 = E.get((t, f, '1.0'), {}), E.get((t, f, '0.6'), {})
        cells = []
        for it in ['배추', '무', '양파', '전체']:
            x, y = a1.get(it, '?'), a6.get(it, '?')
            try:
                mark = '↓' if float(y[:-1]) < float(x[:-1]) else ('↑' if float(y[:-1]) > float(x[:-1]) else '=')
            except Exception:
                mark = ' '
            cells.append('%s→%s %s' % (x, y, mark))
        print('%-9s %-4s %-16s %-16s %-16s %-16s' % (LBL[t], f, *cells))
print()
print('↓ 오차가 줄었다 · ↑ 늘었다')
