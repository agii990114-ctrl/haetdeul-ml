"use client";

/**
 * agent 결과 표시.
 *
 * ★ **판정을 화면이 다시 계산하지 않는다.** 정상/주의/이상은 agent 가 정하고
 *   화면은 그 글자를 그대로 쓴다. 화면이 자기 기준으로 색을 정하기 시작하면,
 *   agent 가 "이상" 이라 한 것이 화면에서 초록으로 보일 수 있다.
 */

import type { AgentReport, Finding } from "@/lib/types";

const TONE: Record<string, { chip: string; dot: string }> = {
  정상: { chip: "bg-accent-wash text-accent-ink", dot: "bg-accent" },
  주의: { chip: "bg-gold-wash text-gold", dot: "bg-gold" },
  이상: { chip: "bg-warn-wash text-warn", dot: "bg-warn" },
};

export function Verdict({ level }: { level: string }) {
  const t = TONE[level] ?? { chip: "bg-sunk text-muted", dot: "bg-faint" };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-semibold ${t.chip}`}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${t.dot}`} />
      {level}
    </span>
  );
}

function FindingCard({ f }: { f: Finding }) {
  return (
    <li className="rounded-lg border border-line bg-surface p-3.5">
      <div className="flex items-start gap-2.5">
        <Verdict level={f.level} />
        <p className="m-0 flex-1 text-[13.5px] font-semibold leading-snug">{f.title}</p>
      </div>

      {f.detail && (
        <p className="m-0 mt-2 whitespace-pre-line text-[12px] leading-relaxed text-muted">
          {f.detail}
        </p>
      )}

      {f.numbers.length > 0 && (
        <dl className="mt-2.5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 border-t border-line-soft pt-2.5">
          {f.numbers.map(([k, v], i) => (
            <div key={i} className="contents">
              <dt className="truncate text-[11.5px] text-muted">{k}</dt>
              <dd className="tabular m-0 text-right font-mono text-[11.5px]">{v}</dd>
            </div>
          ))}
        </dl>
      )}

      {f.advice && (
        <p className="m-0 mt-2.5 rounded bg-sunk px-2.5 py-1.5 text-[11.5px] text-accent-ink">
          → {f.advice}
        </p>
      )}
    </li>
  );
}

export function AgentPanel({
  report,
  subtitle,
}: {
  report: AgentReport;
  subtitle?: string;
}) {
  return (
    <section>
      <header className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="m-0 text-[15px] font-semibold">{report.name}</h2>
        <Verdict level={report.verdict} />
        <span className="tabular font-mono text-[11px] text-faint">{report.at}</span>
        {subtitle && <span className="text-[11.5px] text-muted">{subtitle}</span>}
      </header>
      <ul className="m-0 grid list-none gap-2.5 p-0">
        {report.findings.map((f, i) => (
          <FindingCard key={i} f={f} />
        ))}
      </ul>
    </section>
  );
}
