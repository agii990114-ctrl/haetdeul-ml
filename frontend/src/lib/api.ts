/**
 * 우리 백엔드(`backend/main.py`) 클라이언트.
 *
 * ★ **`/api` 는 `next.config.ts` 의 개발 프록시가 백엔드로 넘긴다.** 같은 출처라
 *   CORS 가 없다. 배포(정적 export)에는 프록시가 없으므로 `NEXT_PUBLIC_API_BASE`
 *   로 절대 주소를 준다.
 *
 * ★ **서버가 낸 오류 문장을 그대로 올린다.** 화면이 "오류가 발생했습니다" 로 덮으면
 *   `2025-12-31 의 경락가 예측이 없습니다` 처럼 **무엇을 해야 하는지 알려주는 문장**
 *   이 사라진다. mainproject 화면과 같은 규칙이다.
 */

import type {
  Accuracy,
  AgentReport,
  BaseDate,
  Forecast,
  HistoryDay,
  Meta,
  TargetKind,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`);
  } catch {
    throw new ApiError(
      0,
      "백엔드에 닿지 못했습니다 — `python -m uvicorn backend.main:app --port 8100` 이 떠 있는지 확인해 주세요.",
    );
  }

  const body = await response.text();
  if (!response.ok) {
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
      else if (parsed.detail) detail = JSON.stringify(parsed.detail);
    } catch {
      /* JSON 이 아니면 본문을 그대로 쓴다 */
    }
    throw new ApiError(response.status, detail);
  }
  return JSON.parse(body) as T;
}

/** 시연 기준일. 매입 파트가 이 날짜로 돈다 — mainproject 화면의 `AS_OF` 와 같다. */
export const AS_OF = process.env.NEXT_PUBLIC_AS_OF ?? "2025-12-31";

export const meta = () => call<Meta>("/meta");
export const baseDates = () => call<BaseDate[]>("/forecast/base-dates?limit=90");
/**
 * `showActual` — 실제값을 함께 받을지.
 *
 * 지금은 지난 날짜로 시연하니 정답이 이미 있지만, **실제 운영에서는 예측을
 * 낼 때 정답이 없다.** 끄면 서버가 `actual`·`err_pct` 를 null 로 비워 보낸다.
 */
export const forecast = (baseDt: string, kind: TargetKind, showActual = true) =>
  call<Forecast>(
    `/forecast?base_dt=${encodeURIComponent(baseDt)}&kind=${kind}` +
      `&show_actual=${showActual}`,
  );
export const accuracy = (minLead = 3) => call<Accuracy>(`/accuracy?min_lead=${minLead}`);

/** 데이터 품질 agent — DB 를 훑어 10초쯤 걸린다. 백엔드가 10분 캐시한다. */
export const qualityAgent = (days = 180) => call<AgentReport>(`/quality?days=${days}`);

/** 배치 장애 조사 agent — 규칙 부분만. AI 조사는 부르지 않는다. */
export const batchAgent = () => call<AgentReport>("/agent/batch");

/** 지난 agent 보고서 목록 — 날짜별로 묶여 온다. */
export const agentHistory = () => call<{ dates: HistoryDay[] }>("/agent/history");

/** 보고서 한 개의 내용. 파일 이름만 넘긴다 (경로는 서버가 막는다). */
export const agentReport = (file: string) =>
  call<{ file: string; text: string; is_claude: boolean }>(
    `/agent/report?file=${encodeURIComponent(file)}`,
  );

/** 예측 하나를 왜 그렇게 냈는지. 규칙만 돌아서 빠르다 (AI 안 부름). */
export const explain = (
  baseDt: string,
  item: string,
  kind: TargetKind,
  lead: number,
  showActual = true,
) =>
  call<AgentReport>(
    `/agent/explain?base_dt=${encodeURIComponent(baseDt)}` +
      `&item=${encodeURIComponent(item)}&kind=${kind}&lead=${lead}` +
      `&show_actual=${showActual}`,
  );
