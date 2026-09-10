# Daily Log — 2026-09-04 (Fri)

**Project:** Haetdeul Nongsan · ML team

---

## Summary

**"It exists, and nobody looks at it."** Three defects found the same day had the same
shape: the value was not the problem — the thing that would have said it was wrong sat
where nobody looked. Separately, a model-structure change that passed every fold
reversed on live data, and the list of "combinations we cannot trust" was rewritten.

## 1. ★★ Base dates had been one day stale for eight months

A row with base date D uses only data up to D−1. But the rebuild created base date D
only **after D's own survey value arrived** — so every morning's forecast was built on
yesterday's base date, with a day-old anchor and one day less of horizon.

The purchase team's contract expects `daily[0] = as_of + 1`. It passed on **26 of 248
days.**

Fixed by inserting empty base-date rows from the day after the last observation up to
today, inside the inference-input step only. **The training table did not change by a
single row.**

## 2. ★★ The batch was throwing away its own validation results

The rebuild SQL contains validation queries. The batch ran the file as one block:

```python
cur.execute(sql)
while cur.nextset():
    pass          # ← every validation result disappears here
```

They were only visible when a person ran the SQL by hand. **Check [14] had reported
100% mismatch for a week** (08-27 → 09-04): when ten derived columns were added, the
inference-input step was not updated, and seven columns were entirely NULL.

Fixed: the batch now runs a separate verification file whose results it reads.
`BAD` stops the batch; `WARN` only notifies. **Use `BAD` sparingly — a daily alarm is
an ignored alarm.**

Also added: detection of days the batch never ran, and checks on successful days too.

## 3. [M-13] The "unusable combinations" list was wrong

The backlog said three of nine combinations were unusable. Error history covered only
January and late August — 27 base dates. Measured on those, six of nine "lost to the
anchor"; split by period, six flipped sign.

Backfilled 137 base dates of 2026 (2024–2025 excluded as sealed). With 164 base dates
and 21,734 scored rows:

- Auction and retail: **five of six cells positive with consistent quarterly signs**
  (+10.1% to +16.9%)
- Wholesale: all three at anchor level

**Cause found:** wholesale price is **identical to the previous day on 58–68% of days**.
The anchor is nearly perfect; there is almost nothing to beat. It is a series problem,
not a crop problem.

Also: a blocked combination is replaced by the anchor before logging, so it can never
be evaluated. Re-measured with the block off in shadow mode, wholesale onion was the
**only** wholesale cell positive in all three quarters.

## 4. Per-crop model split — passed every fold, reversed live

Splitting onion auction into its own model passed three folds and the 2σ rule
(+7.19 / +5.48 / +19.20%). Rebuilt under production conditions (7-year training) and
applied to 164 live 2026 base dates:

```
Onion +2.67% · Cabbage −5.70% · Radish +2.64% · Pooled +0.08%
```

No net gain — rejected. **Folds train on 4–6 years; production on 7. The longer the
training, the more pooling pays.** New procedure: structural changes must also be
checked against 2026 live.

## 5. Other

- Drift detection [I-04]: judged by losing to the anchor, in percentage points
- Credentials consolidated into one root `.env` [S-01]
- English documents: development progress record and troubleshooting casebook
- Eight replies to the purchase team, including adding `band_method` to the handoff
  table and delivering the D+14 width distribution

## Sources

- `진행기록/있는데_아무도_안본다_20260904.md`
- `진행기록/M13_못쓰는조합_재정의_20260904.md`
- `진행기록/daily_log_20260902-04_EN.md`
- git history of 2026-09-04 (#17–#25)
