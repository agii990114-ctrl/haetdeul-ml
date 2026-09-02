"use client";

/**
 * 지난 agent 결과를 날짜별로 본다.
 *
 * 기록은 **파일이 원본**이다 (`진행기록/agent_logs/`). DB 에 또 넣지 않는다 —
 * 두 곳에 있으면 갈라지고, 어느 쪽이 맞는지 아무도 모르게 된다.
 *
 * 두 종류가 섞여 있다.
 *   규칙    quality_agent · batch_agent 가 남긴 것. 판정(정상/주의/이상)이 있다
 *   Claude  매일 09:23 에 무인으로 돌며 원인까지 조사한 것. 판정 대신 글이다
 */

import { useEffect, useState } from "react";

import { ReportBody } from "./ReportBody";
import { Verdict } from "./AgentPanel";
import * as api from "@/lib/api";
import type { HistoryDay, HistoryItem } from "@/lib/types";

function Body({ file, isMarkdown }: { file: string; isMarkdown: boolean }) {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    //  ★ 여기서 setText(null)/setErr(null) 로 비우지 않는다. 파일이 바뀔 때마다
    //    effect 가 다시 도는데, 비우는 순간 화면이 깜빡인다. 새 결과가 오면
    //    어차피 덮인다.
    let alive = true;
    api
      .agentReport(file)
      .then((r) => {
        if (alive) {
          setText(r.text);
          setErr(null);
        }
      })
      .catch((e) => {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      });
    //  이미 다른 파일로 넘어갔으면 늦게 온 답을 버린다.
    return () => {
      alive = false;
    };
  }, [file]);

  if (err) return <p className="m-0 p-4 text-[12px] text-warn">{err}</p>;
  if (text === null) return <p className="m-0 p-4 text-[12px] text-muted">읽는 중…</p>;

  //  .md(Claude 점검)는 문서로, .txt(규칙 보고서)는 줄 맞춤 그대로.
  //  섞어서 한 방식으로 그리면 한쪽이 깨진다.
  return <ReportBody text={text} isMarkdown={isMarkdown} />;
}

export function AgentHistory() {
  const [days, setDays] = useState<HistoryDay[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api
      .agentHistory()
      .then((d) => {
        setDays(d.dates);
        //  가장 최근 날의 Claude 점검을 기본으로 펼친다. 없으면 첫 보고서.
        const first = d.dates[0];
        if (first) {
          const pick = first.reports.find((r) => r.is_claude) ?? first.reports[0];
          if (pick) setOpen(pick.file);
        }
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  if (err)
    return (
      <div className="rounded-lg border border-warn/30 bg-warn-wash px-4 py-3 text-[12.5px] text-warn">
        {err}
      </div>
    );
  if (days === null) return <p className="text-[12.5px] text-muted">기록을 읽는 중…</p>;
  if (days.length === 0)
    return (
      <p className="text-[12.5px] text-muted">
        아직 남은 기록이 없습니다. agent 를 한 번 돌리면 여기에 쌓입니다.
      </p>
    );

  return (
    <div className="grid gap-4">
      {days.map((day) => (
        <section key={day.date}>
          <h3 className="tabular m-0 mb-2 font-mono text-[12.5px] font-semibold text-muted">
            {day.date}
            <span className="ml-2 font-sans text-[11px] font-normal text-faint">
              보고서 {day.reports.length}개
            </span>
          </h3>

          <ul className="m-0 grid list-none gap-1.5 p-0">
            {day.reports.map((r: HistoryItem) => {
              const isOpen = open === r.file;
              return (
                <li
                  key={r.file}
                  className="overflow-hidden rounded-lg border border-line bg-surface"
                >
                  <button
                    onClick={() => setOpen(isOpen ? null : r.file)}
                    className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left hover:bg-sunk"
                  >
                    <span className="tabular w-[62px] shrink-0 font-mono text-[11.5px] text-faint">
                      {r.time ?? "—"}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[13px] font-medium">
                      {r.kind}
                    </span>
                    {r.is_claude ? (
                      <span className="rounded bg-sky-wash px-2 py-0.5 text-[10.5px] font-semibold text-sky">
                        Claude 조사
                      </span>
                    ) : (
                      <span className="rounded bg-sunk px-2 py-0.5 text-[10.5px] text-muted">
                        규칙
                      </span>
                    )}
                    {r.verdict && <Verdict level={r.verdict} />}
                    <span className="tabular w-[52px] shrink-0 text-right font-mono text-[10.5px] text-faint">
                      {(r.bytes / 1024).toFixed(1)}KB
                    </span>
                    <span className="shrink-0 text-[11px] text-faint">{isOpen ? "▲" : "▼"}</span>
                  </button>
                  {isOpen && (
                    <div className="border-t border-line-soft p-2">
                      <Body file={r.file} isMarkdown={r.is_claude} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
