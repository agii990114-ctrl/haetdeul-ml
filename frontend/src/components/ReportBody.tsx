"use client";

/**
 * 보고서 본문 — 형식에 따라 다르게 그린다.
 *
 * 두 종류가 섞여 있다.
 *
 *   `.md`   Claude 무인 점검. 제목·표·굵은 글씨가 있는 **문서**다
 *           → 마크다운으로 그린다
 *
 *   `.txt`  quality_agent · batch_agent 가 남긴 것.
 *           수치가 세로로 줄 맞춰져 있는 **고정폭 글**이다
 *           → 그대로 보여준다. 마크다운으로 그리면 줄 맞춤이 깨진다
 *
 * ★ 원본 HTML 은 허용하지 않는다 (react-markdown 의 기본값). 보고서는
 *   우리가 만든 것이지만, AI 가 쓴 글이 그대로 화면에 들어오는 통로라
 *   열어둘 이유가 없다.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function ReportBody({ text, isMarkdown }: { text: string; isMarkdown: boolean }) {
  if (!isMarkdown) {
    return (
      <pre className="tabular m-0 max-h-[560px] overflow-auto whitespace-pre-wrap break-words rounded bg-sunk p-4 font-mono text-[11.5px] leading-relaxed">
        {text}
      </pre>
    );
  }

  return (
    <div className="max-h-[640px] overflow-auto rounded bg-surface px-4 py-3">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h1 className="m-0 mb-3 mt-1 text-[16px] font-bold" {...p} />,
          h2: (p) => (
            <h2
              className="m-0 mb-2 mt-5 border-b border-line pb-1 text-[14px] font-semibold"
              {...p}
            />
          ),
          h3: (p) => <h3 className="m-0 mb-1.5 mt-4 text-[13px] font-semibold" {...p} />,
          p: (p) => <p className="m-0 mb-2 text-[12.5px] leading-relaxed" {...p} />,
          ul: (p) => <ul className="m-0 mb-2 list-disc pl-5 text-[12.5px]" {...p} />,
          ol: (p) => <ol className="m-0 mb-2 list-decimal pl-5 text-[12.5px]" {...p} />,
          li: (p) => <li className="mb-0.5 leading-relaxed" {...p} />,
          strong: (p) => <strong className="font-semibold text-ink" {...p} />,
          blockquote: (p) => (
            <blockquote
              className="m-0 mb-2 border-l-[3px] border-accent/40 bg-accent-wash/40 py-1.5 pl-3 text-[12px] text-muted"
              {...p}
            />
          ),
          //  표는 가로로 넘칠 수 있다. 페이지 전체가 밀리지 않게 표만 스크롤한다.
          table: (p) => (
            <div className="mb-3 overflow-x-auto">
              <table className="tabular w-full border-collapse text-[11.5px]" {...p} />
            </div>
          ),
          th: (p) => (
            <th
              className="border border-line bg-sunk px-2 py-1 text-left font-semibold"
              {...p}
            />
          ),
          td: (p) => <td className="border border-line px-2 py-1 align-top" {...p} />,
          code: ({ children, ...rest }) => (
            <code
              className="rounded bg-sunk px-1 py-0.5 font-mono text-[11px] text-accent-ink"
              {...rest}
            >
              {children}
            </code>
          ),
          //  코드 블록 안에는 줄 맞춘 표가 들어 있다. 줄바꿈을 건드리지 않는다.
          pre: (p) => (
            <pre
              className="tabular mb-3 overflow-x-auto rounded bg-sunk p-3 font-mono text-[11px] leading-relaxed"
              {...p}
            />
          ),
          hr: () => <hr className="my-4 border-line" />,
          a: (p) => <a className="text-sky underline" {...p} />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
