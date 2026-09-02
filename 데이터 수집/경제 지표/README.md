# ECOS 경제변수 CSV 자동 수집기

한국은행 ECOS와 KDI에서 경제변수를 받아, 기존 영문판과 동일한 12개 컬럼의 일별 CSV를 생성하는 Python CLI 도구입니다.

- 기본 시작일: `2015-01-01`
- 기본 종료일: M2·EPU·PPI·CPI가 모두 존재하는 최신 공통 기준월 말일과 오늘 중 빠른 날짜
- 기본 결과: `output/economic_variables_daily.csv`
- 필요 환경: Python 3.10 이상, 인터넷 연결, 한국은행 ECOS 인증키
- 별도 Python 패키지 설치: 필요 없음

## 1. 인증키 입력

`.env.example`을 `.env`로 복사합니다.

macOS/Linux:

```bash
cp .env.example .env
```

Windows 명령 프롬프트:

```bat
copy .env.example .env
```

생성된 `.env`를 열어 아래 등호 뒤에 발급받은 키를 입력합니다.

```dotenv
ECOS_API_KEY=실제_발급키
```

운영체제 환경변수 `ECOS_API_KEY`가 설정되어 있으면 `.env`보다 우선합니다. 도구는 인증키를 화면이나 CSV에 출력하지 않으며 실행 후에도 `.env`를 삭제하지 않습니다. `.gitignore`에는 `.env`가 포함되어 있습니다.

## 2. 실행

도구 폴더에서 다음 명령을 실행합니다.

```bash
python3 fetch_economic_variables.py
```

Windows에서 `python3` 명령이 없으면 다음과 같이 실행합니다.

```bat
python fetch_economic_variables.py
```

정상 완료 시 다음 파일이 안전하게 생성 또는 교체됩니다.

```text
output/economic_variables_daily.csv
```

새 데이터는 같은 폴더의 임시 파일에 먼저 기록됩니다. 컬럼·행·날짜·결측값 검증을 통과한 경우에만 기존 CSV를 교체하므로, 수집이나 검증이 실패해도 기존 CSV는 유지됩니다.

## 3. 실행 옵션

```text
--start-date YYYY-MM-DD  시작일, 기본 2015-01-01
--end-date YYYY-MM-DD    종료일, 생략하면 최신 공통 기준월 기준으로 자동 결정
--output PATH            결과 CSV 경로
--env-file PATH          ECOS_API_KEY가 들어 있는 설정 파일
--version                도구 버전 표시
```

2015~2021 재생성:

```bash
python3 fetch_economic_variables.py --end-date 2021-12-31
```

출력 위치 변경:

```bash
python3 fetch_economic_variables.py --output ./data/economic_variables_daily.csv
```

다른 설정 파일 사용:

```bash
python3 fetch_economic_variables.py --env-file /safe/path/ecos.env
```

`--end-date`에 아직 발표되지 않은 기준월이 포함되거나 오늘 이후 날짜를 지정하면 결측값을 만들지 않고 오류로 종료합니다.

## 4. CSV 컬럼

기존 영문판의 이름과 순서를 변경하지 않습니다.

| 순서 | 컬럼 | 의미 |
|---:|---|---|
| 1 | `date` | 달력일 기준 날짜 (`YYYY-MM-DD`) |
| 2 | `gov_bond_3y_pct` | 국고채 3년 유통수익률(연 %) |
| 3 | `gov_bond_observation_date` | 사용된 국고채 값의 실제 관측일 |
| 4 | `gov_bond_is_observed` | 당일 관측이면 1, 직전값 전달이면 0 |
| 5 | `m2_yoy_pct` | M2 평잔 원계열 전년동월비(%) |
| 6 | `m2_reference_month` | M2 기준월 (`YYYYMM`) |
| 7 | `epu_index` | KDI 한국 경제정책 불확실성지수 |
| 8 | `epu_reference_month` | EPU 기준월 (`YYYYMM`) |
| 9 | `ppi_index_2020_100` | 생산자물가지수 총지수(2020=100) |
| 10 | `ppi_reference_month` | 생산자물가지수 기준월 (`YYYYMM`) |
| 11 | `cpi_yoy_pct` | 소비자물가지수 총지수 전년동월비(%) |
| 12 | `cpi_reference_month` | 소비자물가지수 기준월 (`YYYYMM`) |

연·월·일 분리 컬럼이나 한글 컬럼은 추가하지 않습니다.

## 5. 수집 및 일별 정렬 규칙

| 변수 | 출처 및 코드 | 일별 정렬 |
|---|---|---|
| 국고채 3년 | ECOS `817Y002` / `010200000` / 일 | 비거래일은 직전 관측값 전달 |
| M2 | ECOS `161Y006` / `BBHA00` / 월 | `(당월/전년동월-1)×100`, 기준월 모든 날짜에 반복 |
| EPU | KDI 한국 EPU / 월 | 기준월 모든 날짜에 반복 |
| 생산자물가지수 | ECOS `404Y014` / `*AA` / 월 | 기준월 모든 날짜에 반복 |
| 소비자물가 | ECOS `901Y009` / `0` / 월 | `(당월/전년동월-1)×100`, 기준월 모든 날짜에 반복 |

- ECOS Open API: https://ecos.bok.or.kr/api/
- KDI 경제불확실성지수: https://eiec.kdi.re.kr/bigdata/index.do

월별 변수는 각 기준월의 모든 달력일에 같은 값을 사용합니다. 따라서 월초 예측에 사용할 때는 해당 월 지표의 실제 공표시점과 모델의 시점 정합성을 별도로 검토해야 합니다.

수집 결과는 기관이 현재 제공하는 수정 후 시계열입니다. 과거 발표 당시의 실시간 빈티지 데이터는 재현하지 않습니다.

## 6. 자동 검증

도구 폴더에서 다음 명령을 실행합니다.

```bash
python3 -m unittest discover -s tests -v
```

인증키가 없으면 네트워크를 사용하지 않는 검증만 수행하고 실 API 회귀 테스트는 자동으로 건너뜁니다. `.env`에 인증키를 넣은 뒤 같은 명령을 실행하면 2015~2021 실 API 결과가 포함된 기준 CSV와 일치하는지도 검사합니다.

검증 항목:

- 영문 컬럼 12개의 이름과 순서
- 2015~2021 기준 파일의 2,557개 달력일과 데이터 정렬 결과
- 날짜 연속성 및 중복 여부
- 결측값과 비정상 숫자
- 기준월과 날짜의 일치 여부
- 국고채 실제관측일과 당일관측여부의 일치 여부
- HTTP 429·5xx 재시도
- 검증 실패 시 기존 CSV 보존

## 7. 오류 처리

- 네트워크 오류, HTTP 429 및 서버 오류는 최대 4회 지수 백오프로 재시도합니다.
- 잘못된 인증키, ECOS/KDI 응답 구조 변경, 중복 관측, 필수 지표 누락은 오류로 종료합니다.
- 오류 메시지에는 인증키가 포함되지 않습니다.
- 실패한 임시 파일은 제거하고 기존 결과 파일은 보존합니다.
