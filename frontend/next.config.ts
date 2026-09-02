import type { NextConfig } from "next";

/**
 * mainproject 와 같은 방식이다.
 *
 * 개발할 때는 `/api` 로 시작하는 주소를 우리 파이썬 백엔드로 넘겨준다. 같은
 * 출처가 되므로 CORS 를 안 만나도 된다.
 *
 * ★ 포트가 다르다. mainproject 백엔드가 8000, 화면이 3000 을 쓰고 있어서
 *   우리는 **8100 · 3100** 을 쓴다. 같이 띄워도 안 부딪힌다.
 */
const isDev = process.env.NODE_ENV === "development";
/**
 * ★ 8100 이 아니라 8101 이다.
 *
 *   2026-08-31 에 8100 을 잡은 프로세스가 죽었는데 소켓만 남아, **옛 코드로
 *   응답하는 좀비**가 됐다. 새 서버는 "포트가 쓰이는 중" 이라며 못 뜨는데
 *   요청은 계속 200 을 받으니, 새로 만든 API 가 404 로 보였다. 몇 분을
 *   "코드가 왜 반영이 안 되지" 로 헤맸다.
 *
 *   재부팅하면 풀리지만, 그때까지 같은 함정에 또 빠지지 않도록 포트를 옮겼다.
 *   API 가 404 를 내면 **포트를 누가 쥐고 있는지부터** 보라:
 *       netstat -ano | grep ":8102" | grep LISTENING
 */
const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8102";

/**
 * `agentRules: false` — Next 가 `CLAUDE.md`·`AGENTS.md` 를 자동 생성하는 걸 끈다.
 * 우리 저장소 뿌리에 이미 `CLAUDE.md`(프로젝트 지시서)가 있어서, 하위 폴더에
 * 같은 이름이 또 생기면 어느 쪽이 규칙인지 헷갈린다.
 */
/**
 * `allowedDevOrigins` — **localhost 가 아닌 주소로 열면 Next 가 JS 를 막는다.**
 *
 *   사내망 IP 로 열었더니 화면이 안 그려지고 콘솔에
 *   `WebSocket connection to 'ws://…/_next/hmr' failed` 만
 *   쏟아졌다. 웹소켓은 증상이고, 진짜 원인은 그 위에서 **JS 파일 자체가
 *   차단된 것**이다 (`Blocked cross-origin request to Next.js dev resource`).
 *   HTML 은 200 으로 오므로 서버는 멀쩡해 보인다.
 *
 *   개발 서버가 사내망에 열리는 걸 막는 안전장치라서, 우리가 쓰는 주소만
 *   손으로 허용한다. 배포 빌드에는 없는 설정이다.
 */
const nextConfig: NextConfig = isDev
  ? {
      agentRules: false,
      //   ★ 사내망 주소는 코드에 안 쓴다 (2026-09-02 · 공개 저장소로 옮기며).
      //   .env.local 에 NEXT_PUBLIC_DEV_ORIGINS 을 쉼표로 구분해
      //   넣으면 된다 (.env.local.example 참조). 없으면 localhost 만 열린다.
      allowedDevOrigins: [
        ...(process.env.NEXT_PUBLIC_DEV_ORIGINS ?? "").split(",")
          .map((s) => s.trim()).filter(Boolean),
        "localhost", "127.0.0.1",
      ],
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${backendOrigin}/:path*` }];
      },
    }
  : { agentRules: false, output: "export" };

export default nextConfig;
