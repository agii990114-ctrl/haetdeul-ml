"use client";

/**
 * "왜 그렇게 예측했나" 설명 — 팝업으로 뜬다.
 *
 * 원래는 그래프 아래에 붙여 뒀는데, 품목 셋이 세로로 쌓인 위에 설명까지
 * 붙으니 화면이 계속 길어졌다. 팝업이면 **그래프가 제자리에 있는 채로** 본다.
 *
 * ★ **화면이 계산하지 않는다.** 출발점 분해도, 중요도도 전부 백엔드가 DB 와
 *   저장된 모델에서 읽어 온 것이다. 화면은 그리기만 한다.
 */

import { useEffect } from "react";

import { Verdict } from "./AgentPanel";
import * as api from "@/lib/api";
import { useState } from "react";
import type { AgentReport, TargetKind } from "@/lib/types";

export function ExplainPanel({
  baseDt,
  item,
  kind,
  lead,
  showActual = true,
  onClose,
}: {
  baseDt: string;
  item: string;
  kind: TargetKind;
  lead: number;
  /** 끄면 서버가 실제값 줄을 아예 안 넣는다 (운영 모습). */
  showActual?: boolean;
  onClose: () => void;
}) {
  const [rep, setRep] = useState<AgentReport | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    //  늦게 온 답이 새 답을 덮지 않게 막는다.
    let alive = true;
    api
      .explain(baseDt, item, kind, lead, showActual)
      .then((r) => {
        if (alive) {
          setRep(r);
          setErr(null);
        }
      })
      .catch((e) => {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [baseDt, item, kind, lead, showActual]);

  //  Esc 로 닫는다. 팝업을 띄웠으면 키보드로도 빠져나갈 수 있어야 한다.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      //  뒷배경을 누르면 닫힌다. 팝업 안을 눌렀을 때는 안 닫히게 막는다.
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4 sm:p-8"
      role="dialog"
      aria-modal="true"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[620px] rounded-xl border border-line bg-surface shadow-xl"
      >
        <header className="flex items-center gap-2 border-b border-line px-4 py-3">
          <h4 className="m-0 text-[14px] font-semibold">
            왜 이렇게 봤나 — {item} · {lead}영업일 뒤
          </h4>
          {rep && <Verdict level={rep.verdict} />}
          <button
            onClick={onClose}
            aria-label="닫기"
            className="ml-auto rounded px-2 py-1 text-[13px] text-muted hover:bg-sunk"
          >
            ✕
          </button>
        </header>

        <div className="p-4">
          {err && <p className="m-0 text-[12px] text-warn">{err}</p>}
          {!rep && !err && <p className="m-0 text-[12px] text-muted">읽는 중…</p>}

          {rep && (
            <ul className="m-0 grid list-none gap-2 p-0">
              {rep.findings.map((f, i) => (
                <li key={i} className="rounded border border-line bg-paper p-3">
                  <p className="m-0 text-[12.5px] font-semibold leading-snug">{f.title}</p>
                  {f.detail && (
                    <p className="m-0 mt-1.5 whitespace-pre-line font-mono text-[11px] leading-relaxed text-muted">
                      {f.detail}
                    </p>
                  )}
                  {f.numbers.length > 0 && (
                    <dl className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 border-t border-line-soft pt-2">
                      {f.numbers.map(([k, v], j) => (
                        <div key={j} className="contents">
                          <dt className="truncate text-[11px] text-muted">{k}</dt>
                          <dd className="tabular m-0 text-right font-mono text-[11px]">{v}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                  {f.advice && (
                    <p className="m-0 mt-2 text-[11px] font-semibold text-warn">→ {f.advice}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
