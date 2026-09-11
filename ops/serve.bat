@echo off
REM ============================================================
REM  ML 콘솔 백엔드를 띄운다  (2026-09-10)
REM
REM  왜 이 파일이 생겼나
REM    지금까지 사람이 손으로 uvicorn 을 쳤고, 기본값이 127.0.0.1 이었다.
REM    127.0.0.1 은 **그 프로그램이 도는 컴퓨터 자신**만 가리킨다.
REM    그래서 다른 컴퓨터에서 화면을 열면 8102 에 붙지 못했다.
REM    주소를 바르게 적어도 안 된다 - 문 자체가 안 열려 있기 때문이다.
REM
REM  주소는 .env 에 있다
REM    ML_CONSOLE_HOST   어느 문을 여나  (0.0.0.0 이면 랜에서도 붙는다)
REM    ML_CONSOLE_PORT   몇 번 문인가    (8102)
REM
REM  ★ 0.0.0.0 은 «아무 데서나 붙어라» 가 아니라 «이 컴퓨터의 모든 랜카드로
REM    받아라» 는 뜻이다. 사내망 안에서만 보인다.
REM
REM  건너편(mainproject) 은 ML_CONSOLE_ORIGIN 으로 이 주소를 찾는다.
REM  mainproject\backend\.env 에 있다. 양쪽을 같이 맞춰야 한다.
REM ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set ROOT=%~dp0..
cd /d "%ROOT%"

REM  기본값 - .env 에 없을 때만 쓴다
set ML_CONSOLE_HOST=0.0.0.0
set ML_CONSOLE_PORT=8102

REM  .env 에서 두 줄만 읽는다. 주석(#)과 빈 줄은 건너뛴다.
REM  ※ 접속 정보는 .env 에만 둔다 - 이 파일에는 안 적는다.
if exist "%ROOT%\.env" (
  for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT%\.env") do (
    set "K=%%a"
    if "!K:~0,1!" neq "#" (
      if /i "!K!"=="ML_CONSOLE_HOST" set "ML_CONSOLE_HOST=%%b"
      if /i "!K!"=="ML_CONSOLE_PORT" set "ML_CONSOLE_PORT=%%b"
    )
  )
)

set PY=C:\Users\403\AppData\Local\Programs\Python\Python311\python.exe

echo ML 콘솔 백엔드를 띄웁니다.
echo   주소  http://%ML_CONSOLE_HOST%:%ML_CONSOLE_PORT%
echo.
echo   같은 컴퓨터에서   http://127.0.0.1:%ML_CONSOLE_PORT%/health
echo   다른 컴퓨터에서   http://^<이 컴퓨터의 랜 주소^>:%ML_CONSOLE_PORT%/health
echo.
echo   ★ 안 붙으면 방화벽을 보세요. 윈도우가 처음 뜰 때 묻습니다 -
echo     «개인 네트워크» 를 허용해야 사내망에서 보입니다.
echo.

"%PY%" -m uvicorn backend.main:app --host %ML_CONSOLE_HOST% --port %ML_CONSOLE_PORT%
