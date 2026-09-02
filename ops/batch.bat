@echo off
REM ============================================================
REM  run_batch.py wrapper for Windows Task Scheduler
REM
REM  Why a wrapper instead of calling python.exe directly:
REM    - Task Scheduler's "start in" is easy to forget; a wrong cwd
REM      makes run_batch.py look for .env in C:\Windows\system32.
REM    - stdout must land in a file. A scheduled task that fails
REM      with no log is a task nobody can debug.
REM    - exit code must reach the scheduler so "last result" is
REM      meaningful in taskschd.msc.
REM
REM  Usage:  ops\batch.bat [args passed to run_batch.py]
REM ============================================================
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set ROOT=%~dp0..
set PY=C:\Users\403\AppData\Local\Programs\Python\Python311\python.exe
set LOGDIR=%~dp0logs

for /f "tokens=1-6 delims=-/:. " %%a in ("%date% %time%") do set TS=%%a%%b%%c_%%d%%e%%f
set TS=%TS: =0%
set LOG=%LOGDIR%\batch_%TS%.log

cd /d "%ROOT%"
echo [start] %date% %time%  args=%* > "%LOG%"
"%PY%" run_batch.py %* >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
echo [end] %date% %time%  exit=%RC% >> "%LOG%"

REM keep 30 days of logs; a batch that runs daily fills a folder fast
forfiles /p "%LOGDIR%" /m batch_*.log /d -30 /c "cmd /c del @path" >nul 2>&1

exit /b %RC%
