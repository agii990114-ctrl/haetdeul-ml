import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans_KR } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";

/**
 * 한글이 본문이라 한글 지원 서체를 쓰고, 가격은 모노스페이스로 줄을 맞춘다.
 * mainproject 와 같은 서체다.
 */
const sans = IBM_Plex_Sans_KR({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-plex-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "원가 캣쳐 · 가격 예측 콘솔",
  description: "예측 곡선과 감시 agent 결과를 보는 화면",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ko" className={`${sans.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
