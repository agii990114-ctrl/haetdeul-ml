# -*- coding: utf-8 -*-
import io, re, os, glob
LBL = {'auc': '경락가', 'whsl': '중도매가', 'rtl': '소매가'}
MAP = {'a10': '1.0', 'a08': '0.8', 'a06': '0.6', 'a04': '0.4', 'a02': '0.2'}
E = {}
for p in sorted(glob.glob('results/alpha5_20260828/*.txt')):
    tgt, fold, al = os.path.basename(p).replace('.txt', '').split('_')
    fold, al = fold.replace('fold', ''), MAP[al]
    s = io.open(p, encoding='utf-8').read()
    blk = re.search(r'\[검증 실제 가격 대비 오차\](.*?)(?:\[검증 리드)', s, re.S)
    d = {}
    if blk:
        for line in blk.group(1).splitlines():
            f = line.split()
            if len(f) >= 4 and f[0] in ('무', '배추', '양파', '전체'):
                d[f[0]] = f[3]
    E[(tgt, fold, al)] = d

ALS = ['1.0', '0.8', '0.6', '0.4', '0.2']
print('[실제 가격 대비 오차율 — 낮을수록 좋음]')
print('%-9s %-5s ' % ('타겟', '폴드') + ' '.join('α=%-5s' % a for a in ALS) + '  최소')
for t in ['auc', 'whsl', 'rtl']:
    for f in ['A', 'B']:
        vals = [E.get((t, f, a), {}).get('전체', '?') for a in ALS]
        try:
            nums = [float(v[:-1]) for v in vals]
            best = ALS[nums.index(min(nums))]
        except Exception:
            best = '?'
        print('%-9s %-5s ' % (LBL[t], f) + ' '.join('%-7s' % v for v in vals) + f'  α={best}')
print()
print('[두 폴드 오차 합 — 낮을수록 좋음]')
print('%-9s ' % '타겟' + ' '.join('α=%-5s' % a for a in ALS) + '  채택')
for t in ['auc', 'whsl', 'rtl']:
    sums = []
    for a in ALS:
        try:
            sums.append(float(E[(t, 'A', a)]['전체'][:-1]) + float(E[(t, 'B', a)]['전체'][:-1]))
        except Exception:
            sums.append(999.0)
    best = ALS[sums.index(min(sums))]
    print('%-9s ' % LBL[t] + ' '.join('%-7.1f' % s for s in sums) + f'  α={best}')
