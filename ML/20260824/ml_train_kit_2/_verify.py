# -*- coding: utf-8 -*-
"""논문 수치 대조. 결과 파일에서 실제 값을 뽑아 논문 주장과 비교한다."""
import io, re, os, glob

def grab(path):
    return io.open(path, encoding='utf-8').read()

D = 'results/remeasure_20260828b'
claims = []          # (논문 위치, 논문 값, 실제 값)

def add(where, claim, actual):
    claims.append((where, str(claim), str(actual)))

# ── §6.1 폴드별 개선율 · 시드 SD ────────────────────────────
want = {('auc','A'):('-3.0','0.0008'), ('auc','B'):('+6.0','0.0007'),
        ('whsl','A'):('+14.8','0.0014'), ('whsl','B'):('+9.3','0.0014'),
        ('rtl','A'):('+16.1','0.0007'), ('rtl','B'):('+9.1','0.0003')}
for (t, f), (imp, sd) in want.items():
    s = grab(f'{D}/{t}_fold{f}.txt')
    m = re.search(r'baseline 대비 ([+-][\d.]+)%', s)
    d = re.search(r'시드별 [\d.]+ ± ([\d.]+)', s)
    add(f'§6.1 {t} fold{f} 개선율', imp + '%', m.group(1) + '%' if m else 'X')
    add(f'§6.1 {t} fold{f} 시드SD', '±' + sd, '±' + d.group(1)[:6] if d else 'X')

# ── §3.5 밴드 폭 중앙값 ────────────────────────────────────
for t, w in [('auc', '64.4'), ('whsl', '46.3'), ('rtl', '22.9')]:
    s = grab(f'{D}/{t}_foldA.txt')
    m = re.search(r'폭 중앙값 ([\d.]+)%', s)
    add(f'§3.5 {t} 밴드폭', w + '%', m.group(1) + '%' if m else 'X')

# ── §5.6 수정 후 WMAPE ─────────────────────────────────────
for f, v in [('A', '0.1754'), ('B', '0.1904')]:
    s = grab(f'{D}/auc_fold{f}.txt')
    m = re.search(r'앙상블 ([\d.]+)', s)
    add(f'§5.6 auc fold{f} WMAPE', v, m.group(1) if m else 'X')

# ── §5.6 수정 전 WMAPE (앞 실행 폴더) ──────────────────────
for f, v in [('A', '0.2247'), ('B', '0.2350')]:
    s = grab(f'results/remeasure_20260828/auc_fold{f}.txt')
    m = re.search(r'앙상블 ([\d.]+)', s)
    add(f'§5.6 auc fold{f} 수정전', v, m.group(1) if m else 'X')

# ── §5.6 best_iter 범위 ────────────────────────────────────
for tag, path, want_rng in [('수정후', f'{D}/auc_foldA.txt', '59-98'),
                            ('수정전', 'results/remeasure_20260828/auc_foldA.txt', '230-548')]:
    s = grab(path)
    it = [int(x) for x in re.findall(r'best_iter (\d+)', s)]
    add(f'§5.6 best_iter {tag}', want_rng, f'{min(it)}-{max(it)}' if it else 'X')

# ── §2.2 학습/검증 기준일 ──────────────────────────────────
s = grab(f'{D}/auc_foldA.txt')
m = re.search(r'학습\s+([\d,]+)행.*?고유 기준일 ([\d,]+)', s, re.S)
add('§2.2 학습 고유 기준일', '1,473', m.group(2) if m else 'X')

# ── §2.3 feature 수 ────────────────────────────────────────
for t, n in [('auc', '31'), ('whsl', '31'), ('rtl', '24')]:
    s = grab(f'{D}/{t}_foldA.txt')
    m = re.search(r'feature (\d+)개', s)
    add(f'§2.3 {t} feature 수', n, m.group(1) if m else 'X')

# ── §6.3 리드타임 ──────────────────────────────────────────
s = grab(f'{D}/auc_foldA.txt')
blk = re.search(r'\[검증 리드타임별\](.*?)\[검증 구간별\]', s, re.S).group(1)
lt = {}
for line in blk.strip().splitlines():
    p = line.split()
    if len(p) >= 4 and p[0].isdigit():
        lt[int(p[0])] = p[3]
for h, v in [(3, '+1.7%'), (6, '+4.6%'), (18, '+3.8%')]:
    add(f'§6.3 LT{h} 개선율', v, lt.get(h, 'X'))

# ── §6.4 변동성 구간 ───────────────────────────────────────
m = re.search(r'평상시\s+모델 ([\d.]+) \| baseline ([\d.]+)', s)
add('§6.4 평상시 모델/baseline', '0.1662 / 0.1726', f'{m.group(1)} / {m.group(2)}' if m else 'X')
m = re.search(r'변동기 상위10%\s+모델 ([\d.]+) \| baseline ([\d.]+)', s)
add('§6.4 변동기 모델/baseline', '0.2746 / 0.2602', f'{m.group(1)} / {m.group(2)}' if m else 'X')

ok = bad = 0
print('%-32s %-18s %-18s %s' % ('논문 위치', '논문 값', '실제 값', '판정'))
print('-' * 82)
for w, c, a in claims:
    good = c.replace('±','').replace('%','').replace('+','').lstrip('0') in a.replace('±','').replace('%','').replace('+','').lstrip('0') or c == a
    ok, bad = (ok + 1, bad) if good else (ok, bad + 1)
    print('%-32s %-18s %-18s %s' % (w, c, a, 'OK' if good else '*** 불일치'))
print('-' * 82)
print(f'일치 {ok} · 불일치 {bad}')
