# 2026-09-10 (Thu) — Chwijung Daily Log

> Paste each block into the matching form field. Counts are checked against the form limits.
> A Korean entry for this date was already submitted (status `in_progress`). Replace or skip to avoid a duplicate.

| Field | Value |
|---|---|
| category | `final` |
| status | `completed` |

## title (38/40)
```text
False alarm fixed; rerun buttons added
```

## feature_name (98/100)
```text
Collection-check false alarm, UI rerun controls, remote access, retrain threshold, sequence models
```

## problems (172/200)
```text
A dry-week false alarm halted the batch so Purchase received no forecast, recovery required a manual rerun, and remote users hit HTTP 502 errors from four unrelated causes.
```

## solution (162/200)
```text
Excluded rainfall blanks from the verdict after a 250-day replay, added single-job rerun buttons, and isolated each network cause by measurement before fixing it.
```

## result (180/200)
```text
162 rows re-delivered; false stops 6.8%→0%; remote access restored; retrain threshold cut from 3 weeks to 1; TFT, LSTM and GRU lost to LightGBM in 23 of 24 cells and were rejected.
```

## content (4854/6000)
````markdown
A false alarm stopped the morning batch and the purchase team received no forecast until a manual rerun, so rerun controls were added to the interface. Remote access to the ML screen failed for four separate reasons that presented as the same error. The retraining threshold was found to be inactive for three model combinations. Sequence neural networks were evaluated under the production protocol and rejected, after the pipeline had been verified.

## False-Alarm Investigation

The collection check reported rainfall missingness rising from 54% to 85% and stopped the batch. The weather service leaves rainfall blank on dry days, and the rebuild already interprets blanks as 0 mm, so the blanks were values rather than gaps. The check compared the last seven days with the prior ninety, which included the monsoon, so a dry week resembled an outage. Early-September blank rates range from 11.8% (2019) to 82.9% (2026). Replaying the check over 250 days showed that rainfall would have stopped the batch on 21 of 309 days (6.8%), five times more than all other checks combined. Rainfall was excluded from the verdict while its figure remains visible. The log had also cited the wrong line as the cause, which was noted for correction.

## Rerun Controls

A "Run again" control appears on the batch tab only when the day's run has failed, and a "Refresh" control was added to the AI report. Both invoke the same script as the scheduler, return immediately and poll every three seconds, and allow only one job at a time because the rebuild empties a table.

## Report Display Defects

The interface showed the English draft instead of the Korean report because both files were flagged as the day's report and name ordering selected the draft; a draft flag now separates them. A warning banner appeared on a correct report because ranges written as "4 to 8" did not match the token "4-8"; numbers are now checked individually, and 246 of 246 matched.

## Remote Access: Four Causes

1. The ML server listened only on the local loopback address; address and port were moved to configuration.
2. A new firewall allow rule had no effect, because an earlier block rule for the Python executable took precedence.
3. The proxy never loaded its configuration file, reading the variable once at import time; locally the default happened to be correct, which concealed the defect.
4. One route returned 404 because the development server had not applied a rewrite rule.

Error messages now state whether an address came from configuration or from the default.

## Retraining Threshold

Replaying 32 weeks, the longest run of consecutive poor weeks was two for cabbage auction, onion auction and onion retail, so a three-week threshold could never trigger for them. A false trigger costs only a 2.5-minute candidate build that is discarded if it loses. The threshold was reduced to one week, and wholesale, which is unchanged from the previous day on six days in ten, was excluded from the verdict while its figures remain reported.

## Purchase Coordination

Three replies were sent. The median forecast is the base for margins, not the upper bound. On the same base date, the gate change raised the cabbage upper bound by 21.5% while the market lowered it by 12.2%; the purchase team's measured +6.6% was the net of the two. The delivered current price is the anchor, not a market price. Two anchor discrepancies were traced to the 2026-09-03 data gap, matching within 1 KRW. Re-measured data (9,690 rows) was provided separately, without overwriting delivered records.

## Sequence-Model Comparison

TFT, LSTM and GRU were evaluated on the same rows as LightGBM (folds A and B, three seeds). While building the data, the anchor differed from the previous survey day on 95.6% of Mondays, because auctions run on Saturdays but surveys do not; the last known auction price was added as an input.

| Lead ≥ 3 | Anchor | LightGBM | TFT | LSTM | GRU |
|---|---|---|---|---|---|
| Fold A | 0.1730 | 0.1667 | 0.2341 | 0.2308 | 0.2689 |
| Fold B | 0.2096 | 0.1956 | 0.2873 | 0.3477 | 0.4001 |

Because the networks lost even to the anchor they received as input, the pipeline was checked first: answers aligned on 100% of rows, and disabling early stopping improved GRU only from 0.2464 to 0.2294. With about 1,475 training days, large models overfit within 50 steps. As a side finding, LightGBM also lost to the strongest baseline at leads 0–2 on both folds; this was recorded for evaluation on 2026 data after the value freeze. The networks ran in an isolated environment, because installing them lowered the pandas version used by the batch.

## Lessons Learned

A single symptom can have several independent causes, and each must be confirmed by measurement before a fix is chosen. A result that looks too poor warrants the same scrutiny as one that looks too good.
````

---

*Sources (not for pasting): git history of 2026-09-10 · mainproject #492, #497 · `연동/20260910/` · `진행기록/시퀀스모델비교_TFT_LSTM_GRU_20260910.md` · `실험결과/시퀀스모델_20260910/`*
