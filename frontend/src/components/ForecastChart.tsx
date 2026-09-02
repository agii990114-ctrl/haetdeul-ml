"use client";

/**
 * 예측 곡선.
 *
 * 라이브러리를 안 쓰고 SVG 로 직접 그린다. 선 하나 그리자고 차트 라이브러리를
 * 받으면 화면이 무거워지고, 무엇보다 **그 라이브러리가 값을 어떻게 다루는지**
 * 우리가 모르게 된다. 없는 값을 0 으로 이어 그리는 라이브러리가 흔하다.
 *
 * ★ **없는 값은 선을 끊는다.** 채점 안 된 날은 실제값이 없다. 그걸 0 으로
 *   내리거나 앞뒤를 이어버리면 "가격이 떨어졌다" 로 읽힌다.
 */

import type { ForecastRow } from "@/lib/types";

const W = 720;
const H = 260;
const PAD = { top: 16, right: 16, bottom: 34, left: 52 };

function niceTicks(lo: number, hi: number, n = 4): number[] {
  if (!isFinite(lo) || !isFinite(hi) || hi <= lo) return [lo];
  const raw = (hi - lo) / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}

export function ForecastChart({
  rows,
  unit,
  gateLead,
  onPick,
  picked,
  origin,
}: {
  rows: ForecastRow[];
  unit: string;
  /**
   * 기준일 그 자체를 그래프 맨 앞에 놓는다.
   *
   * ★ 이건 **예측이 아니라 출발점**이다. 기준일 아침에 우리가 아는 최신
   *   가격이고, 모델은 여기서 얼마나 움직일지를 낸다. 기준일이 12-31 인데
   *   선이 1-2 에서 시작하면 "12-31 은 어디 갔나" 가 된다.
   *   점 모양을 다르게 그려 예측과 구분한다.
   */
  origin?: { date: string; value: number } | null;
  /** 이 리드타임 미만은 모델을 안 쓴다 — 배경을 다르게 칠해 구분한다. */
  gateLead: number;
  /** 점을 누르면 그 리드타임을 알린다. 화면이 설명을 띄운다. */
  onPick?: (lead: number) => void;
  /** 지금 설명이 열려 있는 리드타임. 점을 크게 그려 표시한다. */
  picked?: number | null;
}) {
  if (rows.length === 0) return null;

  //  origin 은 리드타임 0 자리에 놓는다. rows 의 첫 리드타임보다 하나 앞.
  const L0 = rows[0].lead - 1;
  const hasOrigin = !!origin;

  const values = rows.flatMap((r) =>
    [r.lo, r.hi, r.pred, r.actual, r.anchor].filter((v): v is number => v !== null),
  );
  if (origin) values.push(origin.value);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = (hi - lo) * 0.08 || 1;
  const yLo = lo - pad;
  const yHi = hi + pad;

  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const xLo = hasOrigin ? L0 : rows[0].lead;
  const x = (lead: number) =>
    PAD.left + ((lead - xLo) / Math.max(1, rows[rows.length - 1].lead - xLo)) * iw;
  const y = (v: number) => PAD.top + ih - ((v - yLo) / (yHi - yLo)) * ih;

  /** 값이 없는 구간에서 선을 끊는다 — 이어 그리면 없는 값을 지어내는 셈이다. */
  const path = (pick: (r: ForecastRow) => number | null) => {
    let d = "";
    let pen = false;
    for (const r of rows) {
      const v = pick(r);
      if (v === null) {
        pen = false;
        continue;
      }
      d += `${pen ? "L" : "M"}${x(r.lead).toFixed(1)} ${y(v).toFixed(1)} `;
      pen = true;
    }
    return d.trim();
  };

  const band = (() => {
    const up = rows.filter((r) => r.hi !== null);
    const dn = [...rows].reverse().filter((r) => r.lo !== null);
    if (up.length === 0) return "";
    return (
      up.map((r, i) => `${i ? "L" : "M"}${x(r.lead)} ${y(r.hi as number)}`).join(" ") +
      " " +
      dn.map((r) => `L${x(r.lead)} ${y(r.lo as number)}`).join(" ") +
      " Z"
    );
  })();

  const gateX = x(Math.min(gateLead, rows[rows.length - 1].lead));
  const hasActual = rows.some((r) => r.actual !== null);

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
           aria-label="예측 곡선">
        {/* 게이트 구간 — 모델이 아니라 앵커가 그대로 나가는 자리 */}
        {gateLead > rows[0].lead && (
          <rect x={PAD.left} y={PAD.top} width={Math.max(0, gateX - PAD.left)} height={ih}
                fill="var(--color-sunk)" />
        )}

        {niceTicks(yLo, yHi).map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)}
                  stroke="var(--color-line-soft)" strokeWidth={1} />
            <text x={PAD.left - 8} y={y(t) + 3.5} textAnchor="end"
                  className="tabular" fontSize={10} fill="var(--color-faint)">
              {Math.round(t).toLocaleString()}
            </text>
          </g>
        ))}

        {band && <path d={band} fill="var(--color-accent)" opacity={0.11} />}

        {/* 출발점(앵커) — 여기서 얼마나 움직인다고 봤는지가 한눈에 보인다 */}
        {rows[0].anchor !== null && (
          <line x1={PAD.left} x2={W - PAD.right} y1={y(rows[0].anchor)} y2={y(rows[0].anchor)}
                stroke="var(--color-faint)" strokeWidth={1} strokeDasharray="2 3" />
        )}

        {/* 출발점에서 첫 예측까지 잇는 선. 점선으로 그려 '예측 구간이 아님' 을 표시 */}
        {origin && rows[0].pred !== null && (
          <line x1={x(L0)} y1={y(origin.value)} x2={x(rows[0].lead)} y2={y(rows[0].pred)}
                stroke="var(--color-accent)" strokeWidth={2} strokeDasharray="3 3"
                opacity={0.6} />
        )}
        <path d={path((r) => r.pred)} fill="none" stroke="var(--color-accent)" strokeWidth={2} />
        {hasActual && (
          <path d={path((r) => r.actual)} fill="none" stroke="var(--color-warn)"
                strokeWidth={2} strokeDasharray="5 3" />
        )}

        {origin && (
          <circle cx={x(L0)} cy={y(origin.value)} r={4} fill="var(--color-surface)"
                  stroke="var(--color-accent)" strokeWidth={2}>
            <title>{`${origin.date} · 기준일
출발점 ${Math.round(origin.value).toLocaleString()}${unit}
(예측이 아니라 이 날 아는 값)`}</title>
          </circle>
        )}

        {rows.map((r) => (
          <g key={r.lead}>
            {r.pred !== null && (
              <circle
                cx={x(r.lead)}
                cy={y(r.pred)}
                r={picked === r.lead ? 5.5 : 2.6}
                fill="var(--color-accent)"
                stroke={picked === r.lead ? "var(--color-surface)" : "none"}
                strokeWidth={picked === r.lead ? 2 : 0}
                style={{ cursor: onPick ? "pointer" : "default" }}
                onClick={() => onPick?.(r.lead)}
              >
                <title>
                  {`LT${r.lead} · ${r.target_dt}\n예측 ${Math.round(r.pred).toLocaleString()}${unit}` +
                    (r.actual !== null
                      ? `\n실제 ${Math.round(r.actual).toLocaleString()}${unit} (오차 ${r.err_pct?.toFixed(1)}%)`
                      : "\n실제 — 아직 채점 안 됨") +
                    (r.gated ? "\n※ 모델 미사용 — 출발점 그대로" : "")}
                </title>
              </circle>
            )}
            {r.actual !== null && (
              <circle cx={x(r.lead)} cy={y(r.actual)} r={2.6} fill="var(--color-warn)" />
            )}
          </g>
        ))}

        {origin && (
          <text x={x(L0)} y={H - 12} textAnchor="middle" className="tabular"
                fontSize={9.5} fontWeight={600} fill="var(--color-accent-ink)">
            {origin.date.slice(5)}
          </text>
        )}
        {rows.map((r, i) =>
          i % 2 === 0 ? (
            <text key={r.lead} x={x(r.lead)} y={H - 12} textAnchor="middle"
                  className="tabular" fontSize={9.5} fill="var(--color-faint)">
              {r.target_dt.slice(5)}
            </text>
          ) : null,
        )}
      </svg>

      <figcaption className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 bg-accent" />예측
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-4 bg-accent/15" />예측 범위
        </span>
        {hasActual && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 border-t-2 border-dashed border-warn" />실제
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-accent bg-surface" />
          기준일 출발점 (예측 아님)
        </span>
        {gateLead > 1 && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-4 bg-sunk" />
            모델 미사용 (LT{gateLead} 미만)
          </span>
        )}
      </figcaption>
    </figure>
  );
}
