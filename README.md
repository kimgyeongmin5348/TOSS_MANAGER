# TOSS_MANAGER

토스증권 Open API 1.2.14, Streamlit, TiDB를 이용한 개인 포트폴리오 분석의 조회 전용 스타터입니다.

## 가장 먼저 할 일

첨부 이미지에 노출된 Client Secret은 즉시 토스증권에서 **재발급**하세요. 노출된 키는 더 이상 사용하지 마세요. 새 키는 `.env`에만 넣고, 노트북 출력·소스·Git에 남기지 않습니다. 토스증권 설정에서 이 컴퓨터/서버의 공인 IP도 허용해야 합니다(미등록 IP는 403).

```powershell
Copy-Item .env.example .env
# .env를 열어 새 Client ID/Secret 입력
uv sync
uv run jupyter lab
```

Jupyter가 환경에 없다면 `uv add --dev jupyter` 후 실행합니다. Streamlit 화면은 다음 명령으로 엽니다.

```powershell
uv run streamlit run app.py
```

## 데이터가 흐르는 방식

1. `Settings.from_env()`가 `.env`에서 인증정보를 읽습니다. 값 자체는 로그에 출력하지 않습니다.
2. 첫 조회 때 `POST /oauth2/token`에 `application/x-www-form-urlencoded` 형식으로 인증정보를 보내 액세스 토큰을 받습니다.
3. 이후 요청은 `Authorization: Bearer ...`를 사용합니다. 토큰은 메모리에 캐시하며, 만료 60초 전에만 재발급합니다. 토스 명세상 재발급하면 기존 토큰이 즉시 무효가 되므로 프로세스마다 불필요하게 재발급하면 안 됩니다.
4. `GET /api/v1/accounts`의 `accountSeq`를 얻고, 개인 데이터 요청에는 `X-Tossinvest-Account` 헤더로 전달합니다.
5. API의 JSON 원본은 응답 확인용으로 유지하고, `transform.py`가 중첩 구조를 pandas DataFrame의 평면 구조로 바꿉니다.
6. 정규화된 DataFrame은 즉시 분석하거나 TiDB에 저장합니다. 보유자산은 시간별 스냅샷, 캔들은 종목·주기·시각별 시계열입니다.
7. Streamlit은 동일한 수집/변환 코드를 재사용해 화면만 담당합니다.

## 프로젝트 구조

```text
app.py                       Streamlit UI
main.py                      Streamlit용 보조 진입점
test.ipynb                   API를 셀 단위로 확인하는 시작 노트북
.env.example                 비밀값 없는 환경변수 양식
toss_manager/config.py       환경변수 검증
toss_manager/client.py       인증 + 조회 전용 HTTP 클라이언트
toss_manager/transform.py    JSON → DataFrame 정규화
toss_manager/database.py     TiDB 스키마 생성과 적재
```

`client.py`에 주문 생성/정정/취소 메서드를 의도적으로 넣지 않았습니다. 조회와 분석이 안정된 뒤 주문 기능은 별도 모듈, 이중 확인, 주문 한도, 감사 로그를 갖춘 다음 추가하는 편이 안전합니다.

## 현재 수집 형식

- 계좌: `accountNo`, `accountSeq`, `accountType`
- 보유자산: 종목/통화/수량/평균매입가/현재가/매입금액/평가금액/손익/수익률/일일손익 + UTC 수집시각
- 현재가: 토스 원본의 `symbol`, ISO 8601 `timestamp`, 문자열 가격, `currency`
- 캔들: `symbol`, `interval`, UTC timestamp, OHLCV, currency

금액을 DB에 저장할 때는 금융 데이터에 부적합한 `FLOAT` 대신 `DECIMAL`을 사용합니다. 분석 화면에서 KRW와 USD를 그대로 더하면 안 되므로 현재 UI는 통화별 구성을 보여줍니다. 전체 원화 환산 자산을 만들 때는 `/api/v1/exchange-rate`의 환율과 적용 시각을 함께 저장해야 재현 가능합니다.

## TiDB 테이블

- `holding_snapshots`: `(account_seq, symbol, captured_at)` 기본키. 시간에 따른 포트폴리오 변화를 남깁니다.
- `candles`: `(symbol, interval_code, timestamp)` 기본키. 같은 봉을 다시 수집하면 upsert합니다.

TiDB Cloud 연결 문자열은 콘솔의 Connect 정보를 따라 작성하세요. 비밀번호에 `@`, `:`, `/` 등이 있으면 URL 인코딩해야 합니다. 운영 단계에서는 DB 계정을 읽기/쓰기로 분리하고 TLS 검증을 유지하세요.

## 다음 확장 순서

1. 환율 수집 및 모든 자산의 KRW 기준 가치 계산
2. 캔들 페이지네이션 수집 작업과 호출 제한/429 재시도
3. 수익률, 변동성, 최대낙폭(MDD), 벤치마크 대비 성과
4. 섹터·국가·통화별 비중 및 리밸런싱 시뮬레이션
5. 스케줄러로 장 마감 후 스냅샷 적재
6. 사용자 로그인과 계좌번호 마스킹

이 앱은 분석용 예제이며 투자 조언이나 수익을 보장하지 않습니다.
