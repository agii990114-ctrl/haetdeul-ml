# Windows 팀원용 설치·실행 설명서

이 설명서는 전달받은 `auction_collector_handoff.zip`을 Windows에서 설치하고, 2015–2025년 초기 데이터를 PostgreSQL에 적재한 뒤 2026년 이후 데이터를 증분 수집하는 방법을 설명합니다.

실제 API 키와 DB 비밀번호는 ZIP에 포함되어 있지 않습니다. 담당자에게 별도로 전달받아 본인 PC의 `.env`에만 저장하세요.

## 1. 준비물

- Windows 10 또는 11
- Python 3.11 이상
- DBeaver Community
- 공공데이터포털 계정과 일반 인증키
- PostgreSQL 접속 정보와 DB 적재 권한

Python을 새로 설치할 때는 설치 화면의 `Add python.exe to PATH`를 체크하세요. 설치 후 PowerShell을 열고 다음 명령으로 확인합니다.

```powershell
py --version
```

`Python 3.11` 이상이 표시되어야 합니다.

## 2. 공공데이터포털 API 신청

[공공데이터포털](https://www.data.go.kr/)에 로그인한 뒤 아래 두 데이터를 검색해 각각 활용신청합니다.

1. `전국 공영도매시장 경매원천정보` — 필수
   - 2026년 이후 일별 경매 거래를 수집할 때 실제로 사용하는 API입니다.
   - 이 API의 활용신청과 승인이 완료되지 않으면 수집 명령을 실행할 수 없습니다.
2. `농축수산물 표준코드` — 권장
   - 품목·시장·등급 코드의 의미를 확인하거나 향후 대상 품목을 확장할 때 사용하는 참고 API입니다.
   - 현재 기본 5개 품목 수집 명령이 직접 호출하는 API는 아니므로, 신청이 늦어져도 기본 수집은 실행할 수 있습니다.

신청 순서:

1. 공공데이터포털 검색창에서 위 데이터명을 검색합니다.
2. 해당 OpenAPI 상세 페이지에서 `활용신청`을 누릅니다.
3. 활용 목적을 입력하고 개발계정으로 신청합니다.
4. 마이페이지의 OpenAPI 개발계정에서 승인 또는 자동승인 상태를 확인합니다.
5. 발급된 `일반 인증키`를 확인합니다. Encoding 키와 Decoding 키 중 어느 키를 제공받았는지 기록해 둡니다.

도구에는 공공데이터포털의 일반 인증키 하나를 다음 환경변수로 입력합니다.

```dotenv
DATA_GO_KR_SERVICE_KEY=발급받은_일반_인증키
```

인증키는 승인 직후 실제 호출이 가능해질 때까지 시간이 조금 걸릴 수 있습니다. 인증 오류가 나면 승인 상태와 인증키를 먼저 확인한 뒤 잠시 후 다시 실행하세요.

## 3. 압축 해제

ZIP을 영문 경로에 압축 해제하는 것을 권장합니다.

```text
C:\auction_collector
```

이후 PowerShell을 열고 해당 폴더로 이동합니다.

```powershell
cd C:\auction_collector
```

## 4. Python 환경 설치

아래 명령을 순서대로 실행합니다. PostgreSQL 적재용 드라이버도 함께 설치됩니다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[postgres]"
```

이 설명서에서는 PowerShell 실행 정책 문제를 피하기 위해 가상환경을 활성화하지 않고 `.venv`의 Python을 직접 실행합니다.

설치 확인:

```powershell
.\.venv\Scripts\python.exe -m auction_collector --help
```

## 5. 환경변수 설정

예제 파일을 `.env`로 복사한 뒤 메모장으로 엽니다.

```powershell
Copy-Item .env.example .env
notepad .env
```

다음 형식으로 값을 입력합니다.

```dotenv
DATA_GO_KR_SERVICE_KEY=본인의_공공데이터포털_인증키
DATABASE_URL=postgresql://전용계정:비밀번호@DB호스트:5432/cost_catcher_raw
DATE_CONCURRENCY=2
```

- `.env`를 메신저, 이메일, Git 저장소에 올리지 마세요.
- 공용 `root` 계정보다는 적재 권한만 가진 전용 계정을 권장합니다.
- 비밀번호에 `@`, `:`, `/`, `#`, `%` 같은 문자가 있으면 URL 인코딩이 필요합니다.
- API 키는 공공데이터포털에서 제공한 일반 인증키를 사용합니다.

## 6. CSV 사전 검증

초기 데이터 파일의 인코딩, 16개 컬럼, 날짜, 숫자값과 중복을 검사합니다.

```powershell
.\.venv\Scripts\python.exe -m auction_collector validate outputs\auction_prices_2015_2025_db.csv
```

마지막 JSON 결과에서 `"status": "ok"`와 `"duplicate_natural_keys": 0`을 확인합니다.

정상 기준은 다음과 같습니다.

- 행 수: `736431`
- 최소 날짜: `2015-01-02`
- 최대 날짜: `2025-12-31`
- 컬럼 수: `16`
- 인코딩: `UTF-8`, BOM 없음

## 7. 최초 1회: DBeaver에서 테이블 생성

이 단계는 DB 담당자 한 명만 최초 1회 실행하면 됩니다.

1. DBeaver에서 대상 PostgreSQL DB에 연결합니다.
2. 연결된 DB를 선택한 상태에서 `SQL 편집기` → `SQL 스크립트 열기`를 선택합니다.
3. 다음 파일을 엽니다.

```text
outputs\auction_prices_2015_2025_postgresql.sql
```

4. 스크립트 전체를 실행합니다. DBeaver 기본 단축키는 `Alt+X`입니다.
5. `public` → `Tables`를 새로고침하고 `auction_prices_daily` 테이블이 생겼는지 확인합니다.

생성 확인 SQL:

```sql
SELECT current_database(), current_user, current_schema();

SELECT to_regclass('public.auction_prices_daily') AS table_name;
```

`table_name`에 `auction_prices_daily`가 표시되면 정상입니다.

## 8. 최초 1회: DBeaver에서 2015–2025 CSV 적재

테이블을 만든 뒤 초기 CSV를 한 번만 적재합니다.

1. DBeaver 왼쪽에서 `public.auction_prices_daily`를 우클릭합니다.
2. `데이터 가져오기(Import Data)`를 선택합니다.
3. 원본 형식으로 `CSV`를 선택합니다.
4. 다음 파일을 선택합니다.

```text
outputs\auction_prices_2015_2025_db.csv
```

5. CSV 설정을 다음과 같이 확인합니다.

   - 인코딩: `UTF-8`
   - 구분자: 쉼표 `,`
   - 첫 행을 컬럼명으로 사용: 체크
   - 빈 문자열 또는 NULL 표시: `NULL`로 처리

6. 컬럼 매핑에서 CSV의 16개 영문 헤더가 같은 이름의 DB 컬럼에 연결되었는지 확인합니다.
7. DB의 `id` 컬럼은 매핑하지 않습니다. PostgreSQL이 자동 생성합니다.
8. 가져오기를 실행하고 완료 메시지를 확인합니다.

적재 후 아래 SQL을 실행합니다.

```sql
UPDATE public.auction_prices_daily
SET grade_code = NULL
WHERE grade_code = '';

SELECT
  COUNT(*) AS row_count,
  MIN(auction_date) AS min_date,
  MAX(auction_date) AS max_date,
  COUNT(*) FILTER (WHERE grade_code IS NULL) AS null_grade_codes
FROM public.auction_prices_daily;
```

결과는 `736431행`, `2015-01-02`, `2025-12-31`이어야 합니다. 숫자가 다르면 증분 실행 전에 적재를 중지하고 담당자에게 확인하세요.

## 9. 2026년 이후 증분 수집 및 DB 적재

초기 데이터 적재가 확인된 뒤 다음 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m auction_collector update --load-postgres
```

기본 동작:

- 기존 CSV의 최종일 다음 날부터 한국시간 기준 어제까지 수집
- 월요일부터 토요일까지 조회하고 일요일은 기본 제외
- 수집 결과를 현재 CSV에 누적
- 이번에 새로 수집한 범위를 PostgreSQL에 upsert
- 완료된 날짜는 캐시에 저장해 재실행 시 불필요한 API 호출 방지

첫 실행 시 기간이 길면 시간이 걸릴 수 있습니다. PowerShell 창을 닫거나 PC가 꺼졌다면 같은 명령을 다시 실행하세요. 완료된 날짜의 캐시를 이어서 사용합니다.

## 10. 자주 사용하는 명령

현재 CSV 검증:

```powershell
.\.venv\Scripts\python.exe -m auction_collector validate outputs\auction_prices_current_db.csv
```

지정 기간만 수집:

```powershell
.\.venv\Scripts\python.exe -m auction_collector collect --start 2026-08-01 --end 2026-08-10
```

지정 기간을 DB에도 upsert:

```powershell
.\.venv\Scripts\python.exe -m auction_collector collect --start 2026-08-01 --end 2026-08-10 --load-postgres
```

일요일도 포함:

```powershell
.\.venv\Scripts\python.exe -m auction_collector update --include-sundays --load-postgres
```

캐시를 무시하고 API를 다시 호출해야 할 때만 `--force`를 사용합니다.

## 11. 결과 파일

`update` 실행 후 다음 파일이 생성됩니다.

- `outputs\auction_prices_current_db.csv`: DB 적재용 UTF-8 무BOM 파일
- `outputs\auction_prices_current_excel.csv`: Excel 확인용 UTF-8 BOM 파일
- `outputs\auction_prices_current_manifest.json`: 행 수, 기간, 해시 등 검증 정보
- `outputs\runs\`: 실행 회차별 증분 결과
- `work\auction_collector_cache\`: 중단 재개용 일자별 캐시

Excel에서는 반드시 `_excel.csv`를 열고, DB에는 `_db.csv`를 사용합니다.

## 12. 실행 후 DB 확인

DBeaver에서 다음 SQL로 최신 적재 상태를 확인합니다.

```sql
SELECT
  COUNT(*) AS row_count,
  MIN(auction_date) AS min_date,
  MAX(auction_date) AS max_date
FROM public.auction_prices_daily;

SELECT item_name, MAX(auction_date) AS latest_date, COUNT(*) AS row_count
FROM public.auction_prices_daily
GROUP BY item_name
ORDER BY item_name;
```

## 13. 오류별 확인 사항

### `py` 또는 Python을 찾을 수 없음

Python 3.11 이상을 설치하고 설치 화면에서 PATH 추가를 체크한 뒤 PowerShell을 다시 여세요.

### `DATA_GO_KR_SERVICE_KEY를 설정하세요`

프로젝트 최상위 폴더의 `.env` 파일명과 API 키를 확인합니다. 파일이 `.env.txt`로 저장되지 않았는지도 확인하세요.

```powershell
Get-ChildItem -Force .env*
```

### PostgreSQL 연결 실패

- DB 호스트와 포트에 접근 가능한 사내망 또는 VPN인지 확인
- DBeaver에서 같은 계정으로 연결되는지 확인
- `.env`의 `DATABASE_URL` 오타와 특수문자 인코딩 확인
- Windows 방화벽과 DB 서버의 접속 허용 IP 확인

### API 429 또는 일시적 서버 오류

도구가 자동으로 재시도합니다. 반복 실패하면 잠시 뒤 같은 명령을 다시 실행하세요.

### 여러 명이 동시에 실행

DB 중복은 upsert로 방지되지만 API 호출과 캐시가 중복될 수 있습니다. 정기 증분 수집은 한 명 또는 하나의 작업 스케줄러만 담당하세요.

## 14. 팀 내 권장 운영 방식

- DB 테이블 생성과 초기 CSV 적재: DB 담당자 1명
- 증분 수집: 담당자 1명 또는 Windows 작업 스케줄러 1개
- 조회·분석 팀원: DBeaver에서 읽기 전용 계정 사용
- `.env`, API 키, DB 비밀번호: 별도 보안 채널로 전달
- 오류 문의 시 비밀번호나 API 키 대신 실행 시각과 오류 메시지만 공유
