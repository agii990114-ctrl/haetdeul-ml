"use client";

/**
 * 재학습 — LangGraph 상태 기계로 도는 쪽.
 *
 * ★ 옆의 `RetrainPanel` 과 **나란히** 둔다. 지금 것을 안 지웠다.
 *
 *   다른 점 둘
 *     ① 상태가 서버 메모리가 아니라 체크포인트(sqlite)에 있다
 *        → **서버가 재시작돼도 작업이 남는다.** 지금 것은 사라진다
 *     ② 검증을 통과 못 하면 **두 번째 물음이 아예 안 나온다**
 *        → 버튼을 띄워 두고 막는 것보다, 물음을 안 내는 편이 낫다
 *
 * ★ 노드 하나도 LLM 을 안 부른다. 여기서 LangGraph 는 **상태 기계**다.
 *   판정은 전부 규칙이다.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, graphAct, graphReset, graphStatus } from "@/lib/api";
import type { GraphStatus } from "@/lib/types";

import { Verdict } from "./AgentPanel";
import { VerifyTable } from "./VerifyTable";

const KIND_LABEL: Record<string, string> = { auc: "경락가", whsl: "중도매가", rtl: "소매가" };

/** 노드 이름 → 사람 말. 화면에 raw 노드명을 그대로 보이지 않는다. */
const NODE_LABEL: Record<string, string> = {
  judge: "판정 중",
  ask_build: "후보를 만들까요",
  build: "후보 만드는 중",
  verify: "견주는 중",
  ask_apply: "바꿀까요",
  apply: "바꾸는 중",
};

function Button({
  onClick, disabled, tone = "plain", children,
}: {
  onClick: () => void; disabled?: boolean;
  tone?: "plain" | "primary" | "warn"; children: React.ReactNode;
}) {
  const skin =
    tone === "primary"
      ? "bg-accent text-white hover:brightness-110"
      : tone === "warn"
        ? "border border-warn text-warn hover:bg-warn-wash"
        : "border border-line text-ink hover:bg-sunk";
  return (
    <button
      type="button" onClick={onClick} disabled={disabled}
      className={`rounded-md px-3 py-1.5 text-[12.5px] font-semibold transition
        disabled:cursor-not-allowed disabled:opacity-40 ${skin}`}
    >
      {children}
    </button>
  );
}

export function RetrainGraphPanel({ kind = "auc" }: { kind?: "auc" | "whsl" | "rtl" }) {
  const [st, setSt] = useState<GraphStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      setSt(await graphStatus(kind));
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  }, [kind]);

  useEffect(() => { void load(); }, [load]);

  //  돌고 있을 때만 물어본다. 끝나면 멈춘다 — 계속 물으면 서버가 논다.
  useEffect(() => {
    if (!st?.running.busy) {
      if (timer.current) clearInterval(timer.current);
      timer.current = null;
      return;
    }
    timer.current = setInterval(() => { void load(); }, 3000);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [st?.running.busy, load]);

  const act = async (answer?: "build" | "apply" | "stop", confirmText?: string) => {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(true);
    try {
      await graphAct(kind, answer);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (err && !st)
    return (
      <p className="m-0 rounded-lg border border-warn bg-warn-wash p-3 text-[12.5px] text-warn">
        {err}
      </p>
    );
  if (!st) return <p className="m-0 text-[12.5px] text-muted">그래프 상태를 읽는 중…</p>;

  const label = KIND_LABEL[kind] ?? kind;
  const running = st.running.busy;
  const asking = st.asking;
  const v = st.values as Record<string, unknown>;
  const done = !running && !asking && st.next.length === 0;
  const where = running
    ? (st.next.map((n) => NODE_LABEL[n] ?? n).join(" · ") || "도는 중")
    : asking
      ? asking.ask
      : done && Object.keys(v).length > 0
        ? "끝났습니다"
        : "시작 전";

  return (
    <section className="space-y-3">
      <header className="flex flex-wrap items-center gap-2">
        <Verdict level={(v.verdict as string) ?? "정상"} />
        <h3 className="m-0 text-[14px] font-semibold">
          {label} — 재학습 흐름 <span className="text-muted">(상태 기계)</span>
        </h3>
        <span className="text-[11px] text-muted">{where}</span>
        <div className="ml-auto flex gap-2">
          {!running && !asking && (
            <Button onClick={() => void act()} disabled={busy} tone="primary">
              판정하기
            </Button>
          )}
          {asking?.ask?.includes("후보") && (
            <Button onClick={() => void act("build")} disabled={busy} tone="primary">
              후보 만들기
            </Button>
          )}
          {asking?.ask?.includes("바꿀까요") && (
            <Button
              onClick={() =>
                void act(
                  "apply",
                  `${label} 운영 모델을 후보로 바꿉니다.\n\n` +
                    "· 지금 것은 통째로 백업됩니다\n" +
                    "· 모델 이름은 안 바뀝니다 — 매입 파트가 이름으로 찾습니다\n\n바꿀까요?",
                )
              }
              disabled={busy}
              tone="primary"
            >
              바꾸기
            </Button>
          )}
          {asking && (
            <Button onClick={() => void act("stop")} disabled={busy}>
              그만두기
            </Button>
          )}
          {done && Object.keys(v).length > 0 && (
            <Button onClick={() => { void graphReset(kind).then(load); }} disabled={busy} tone="warn">
              처음으로
            </Button>
          )}
        </div>
      </header>

      <p className="m-0 text-[11.5px] leading-relaxed text-muted">
        사람이 <b>두 번</b> 누릅니다 — 「후보 만들기」와 「바꾸기」. 그 사이는 자동입니다.
        <br />
        ★ <b>검증을 통과 못 하면 「바꾸기」가 아예 안 나옵니다.</b> 그리고 상태가
        파일에 남아 <b>서버가 재시작돼도 이어집니다.</b>
      </p>

      {err && (
        <p className="m-0 rounded-md border border-warn bg-warn-wash p-2.5 text-[12px] text-warn">
          {err}
        </p>
      )}

      {/* 지금 묻고 있는 것 */}
      {asking && (
        <div className="rounded-lg border border-gold bg-gold-wash p-3.5">
          <p className="m-0 text-[13.5px] font-semibold">★ {asking.ask}</p>
          {asking.hint && (
            <p className="m-0 mt-1.5 text-[12px] leading-relaxed text-muted">{asking.hint}</p>
          )}
          {/*  ★ 표를 **글보다 먼저** 보인다. 「바꿀까요」 에 답하려면
                  숫자를 나란히 봐야 한다. */}
          {asking.items && asking.items.length > 0 && (
            <div className="mt-3">
              <VerifyTable items={asking.items} />
            </div>
          )}
          {asking.verify && (
            <details className="mt-2.5">
              <summary className="cursor-pointer text-[11.5px] text-muted">
                판정 문장 그대로 보기
              </summary>
              <pre className="m-0 mt-1.5 max-h-52 overflow-auto rounded border border-line-soft bg-surface p-2.5 text-[11.5px] leading-relaxed">
                {asking.verify}
              </pre>
            </details>
          )}
        </div>
      )}

      {/*  묻는 중이 아니어도 마지막 검증 표는 남겨 둔다 — 끝난 뒤에
             «왜 안 바꿨나» 를 되짚을 수 있어야 한다. */}
      {!asking && st.verify_items && st.verify_items.length > 0 && (
        <VerifyTable items={st.verify_items} />
      )}

      {/*  지금 상태에 표가 없을 때만 지난 것을 보인다.
           ★ **언제 잰 것인지 반드시 적는다** — 날짜 없이 숫자만 보이면
             지금 판정으로 읽는다. */}
      {!asking && !(st.verify_items && st.verify_items.length) && st.last_verify && (
        <section className="space-y-2">
          <p className="m-0 flex flex-wrap items-baseline gap-x-2 text-[12px] text-muted">
            <b className="text-ink">지난 검증</b>
            <span className="tabular font-mono text-[11.5px]">{st.last_verify.at}</span>
            <span className="text-[11.5px]">
              후보 <span className="font-mono">{st.last_verify.candidate}</span> ·
              {" "}견준 구간 {st.last_verify.eval_from} 부터
            </span>
            <span
              className={`rounded px-2 py-0.5 text-[11px] font-semibold ${
                st.last_verify.passed
                  ? "bg-accent-wash text-accent-ink"
                  : "bg-warn-wash text-warn"
              }`}
            >
              {st.last_verify.passed ? "통과" : "안 바꿨습니다"}
            </span>
          </p>
          <VerifyTable items={st.last_verify.items} />
        </section>
      )}

      {/* 그래프가 들고 있는 값 */}
      {Object.keys(v).length > 0 && (
        <dl className="m-0 grid grid-cols-[minmax(0,auto)_1fr] gap-x-4 gap-y-1 rounded-lg border border-line bg-surface p-3.5 text-[12px]">
          {Object.entries(v).map(([k, val]) => (
            <div key={k} className="contents">
              <dt className="m-0 font-mono text-muted">{k}</dt>
              <dd className="m-0 break-all">{String(val)}</dd>
            </div>
          ))}
        </dl>
      )}

      {/* 돌고 있을 때의 기록 — 실패해도 남는다 */}
      {st.build_tail && (
        <pre className="m-0 max-h-56 overflow-auto rounded-lg border border-line bg-sunk p-3 text-[11px] leading-relaxed">
          {st.build_tail}
        </pre>
      )}
    </section>
  );
}
