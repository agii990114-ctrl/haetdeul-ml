@echo off
REM ============================================================
REM  Claude Code 로 매일 배치를 사후 점검한다  (2026-08-31)
REM
REM  왜 이게 있나
REM    배치는 09:00 에 돌지만, 실패해도 사람이 파일을 안 열면 모른다.
REM    실제로 8/29~8/31 사흘 동안 아무도 몰랐다.
REM    이 스크립트가 09:23 에 Claude 를 불러 결과를 읽고 정리시킨다.
REM
REM  왜 이 창(대화)의 예약이 아니라 작업 스케줄러인가
REM    Claude Code 안의 예약은 세션이 살아 있을 때만 있고 7일이면
REM    만료된다. 창을 닫으면 사라진다. 작업 스케줄러는 창과 무관하다.
REM    이미 batch.bat 가 같은 방식으로 돌고 있다.
REM
REM  로그인
REM    별도 토큰을 만들지 않았다. 이 PC 의 로그인 상태를 그대로 쓴다.
REM    출입증(accessToken)은 몇 시간마다 만료되지만 재발급권이 자동으로
REM    갱신한다 (2026-08-31 12:14 실측: 12:11 만료 → 20:09 로 자동 갱신).
REM    재발급권까지 만료되면 사람이 다시 로그인해야 하고, 그때는
REM    아래 결과 파일이 안 생기므로 run_batch.py 가 경보를 낸다.
REM
REM  ★ 종료코드를 스케줄러에 그대로 넘긴다.
REM    로그인이 끊기면 claude 가 1 을 돌려준다 (실측 확인).
REM    그래도 종료코드만 믿지 않고 결과 파일 유무로 한 번 더 본다.
REM ============================================================
setlocal
chcp 65001 >nul

set ROOT=%~dp0..
set LOGDIR=%~dp0logs
set OUTDIR=%ROOT%\진행기록\agent_logs

for /f "tokens=1-6 delims=-/:. " %%a in ("%date% %time%") do set TS=%%a%%b%%c_%%d%%e%%f
set TS=%TS: =0%
set LOG=%LOGDIR%\claude_check_%TS%.log

REM 오늘 날짜 (YYYY-MM-DD) — 결과 파일 이름에 쓴다
for /f "tokens=1-3 delims=-/. " %%a in ("%date%") do set TODAY=%%a-%%b-%%c

cd /d "%ROOT%"
echo [start] %date% %time% > "%LOG%"

REM  --print  화면 없이 한 번 실행하고 끝낸다
REM  권한은 읽기와 우리 스크립트 실행까지만 연다. 고치는 일은 시키지 않는다 —
REM  v5 재생성이 표를 TRUNCATE 하므로 자동 재실행은 데이터를 날릴 수 있다.
REM  Write 가 있어야 보고서 파일을 만든다. 처음에 빼먹어서 못 만들 뻔했다.
REM  Edit 는 주지 않는다 - 기존 파일을 고칠 일이 없다.
REM  ※ REM 을 ^ 로 이어지는 명령 중간에 넣으면 명령이 통째로 깨진다.
claude --print --permission-mode acceptEdits ^
  --allowedTools "Bash Read Glob Grep Write" ^
  --append-system-prompt "너는 무인 점검 담당이다. 파일을 고치거나 배치를 재실행하지 마라. 조사하고 보고만 한다. 설명은 초등학생도 알아듣게, 숫자는 그대로, 나쁜 소식은 순화하지 마라." ^
  "일별배치 사후 점검이다. 오늘은 %TODAY% 다. 다음을 하고 결과를 '진행기록/agent_logs/%TODAY%_claude_check.md' 에 써라. 파일을 반드시 만들어라 — 그 파일이 없으면 배치가 점검 실패로 본다. (1) 'python agent/batch_agent.py' 를 돌려 오늘 배치 결과를 본다. 실패했으면 어느 단계에서 몇 번째 연속 실패인지, 오류 원문이 무엇인지 적고, 로그와 최근 코드 변경을 직접 뒤져 원인을 찾는다. 고치지는 마라. (2) 'python agent/quality_agent.py --days 180' 을 돌린다. 네 검사가 모두 정상이면 '데이터 품질: 정상' 한 줄로만 적어라. 주의나 이상이 있을 때만 자세히 적어라. (3) 매입 파트 전달표에 오늘 기준일이 들어갔는지 확인한다. 조용할 때 조용해야 진짜 신호가 눈에 띈다. 문제가 없으면 짧게 끝내라." >> "%LOG%" 2>&1

set RC=%ERRORLEVEL%
echo [end] %date% %time%  exit=%RC% >> "%LOG%"

REM  종료코드가 0 이어도 결과 파일이 없으면 실패로 본다.
REM  "실패했다는 말" 보다 "결과가 없다는 사실" 이 더 믿을 만하다.
REM  우리가 두 번 당한 게 전부 '실패했는데 성공처럼 보인' 경우였다.
if not exist "%OUTDIR%\%TODAY%_claude_check.md" (
  echo [경고] 점검 결과 파일이 없습니다: %TODAY%_claude_check.md >> "%LOG%"
  echo         로그인이 끊겼는지 확인하세요 - claude -p "ok" >> "%LOG%"
  exit /b 9
)

forfiles /p "%LOGDIR%" /m claude_check_*.log /d -30 /c "cmd /c del @path" >nul 2>&1
exit /b %RC%
