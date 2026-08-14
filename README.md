# Porto

<sub><b>PORTO</b>는 <b>PORT</b>folio와 <b>O</b>rganizer를 합친 이름으로, 흩어진 투자 자산과 정보를 한곳에서 체계적으로 정리하고 관리해 주는 포트폴리오 매니저를 의미합니다.</sub>

> 토스증권 Open API와 저장 데이터를 연결한 멀티 사용자 포트폴리오 분석 서비스

Porto는 흩어진 계좌·시세·차트 데이터를 하나의 화면에서 확인하고, 접속 환경이 달라져도 마지막으로 저장한 포트폴리오를 다시 볼 수 있도록 만든 개인 투자 관리 서비스입니다. 단순한 실시간 조회 화면에 그치지 않고, **5년 캔들 백필**, **사용자별 데이터 격리**, **오프라인 조회**, **뉴스·재무·기술 분석**, **AI 설명**까지 하나의 데이터 흐름으로 연결했습니다.

분석 결과는 투자 판단을 돕는 정보이며 특정 금융상품의 매수·매도 권유나 수익 보장을 의미하지 않습니다.

## 프로젝트 핵심

| 문제 | Porto의 해결 방식 |
|---|---|
| API 연결이 끊기면 포트폴리오를 볼 수 없음 | TiDB에 계좌별 스냅샷을 저장하여 API Key 없이도 마지막 포트폴리오 제공 |
| 종목별 과거 캔들이 일부만 저장됨 | 최초·최종 일봉 범위를 확인하고 `nextBefore`로 최근 5년을 백필한 뒤 증분 동기화 |
| 여러 사용자의 계좌 데이터가 섞일 위험 | 모든 계좌와 스냅샷을 `user_id`로 연결하고 사용자 보유 종목에 한해 저장 캔들 조회 허용 |
| 숫자 중심의 분석은 이해하기 어려움 | 기술 신호, 유사 패턴 통계, 뉴스 심리, 포트폴리오 위험을 시각 카드로 제공 |
| LLM이 근거 없이 투자 결론을 만들 수 있음 | 규칙 기반 분석 결과를 먼저 계산하고 LLM은 구조화된 근거를 설명하는 역할로 제한 |

## 주요 기능

### 1. 멀티 사용자 계좌 연결

- Porto 이메일과 비밀번호로 회원가입 및 로그인
- 토스증권 Open API 계좌 검증 후 사용자와 계좌 연결
- `(user_id, provider, toss_account_seq)` 복합 유일 키로 계좌 중복 방지
- 계좌번호는 마지막 네 자리만 포함한 마스킹 값으로 저장
- Toss Client ID와 Client Secret은 DB에 저장하지 않고 현재 Streamlit 세션에서만 사용

### 2. 온라인·오프라인 포트폴리오

- 실시간 연결 시 계좌별 보유 종목과 손익 조회
- 최신 포트폴리오를 `portfolio_snapshots`와 `holding_snapshot_items`에 저장
- 다른 PC에서 로그인해도 마지막 저장 포트폴리오, 보유 종목, 평균 단가, 저장 차트 조회
- 저장 시각을 표시하여 실시간 데이터와 명확히 구분
- 사용자 소유 계좌를 거쳐 조회하므로 다른 사용자의 저장 데이터 접근 차단

### 3. 5년 캔들 백필과 증분 동기화

- 종목 상세 화면 진입 즉시 최근 5년 일봉 범위를 확인하고 부족한 구간 수집
- 최초 저장 시 Toss API의 `nextBefore` 페이지네이션으로 과거 데이터 백필
- 5년치가 확보된 뒤에는 DB의 마지막 일봉 이후만 증분 조회
- 장중 변경될 수 있는 마지막 캔들도 다시 upsert
- `(instrument_id, interval_code, candle_at)` 복합 PK로 중복 캔들 방지
- 저장 실패 시에도 API 조회가 성공했다면 최신 차트는 계속 표시
- 공식 1분봉을 5분봉·10분봉으로, 일봉을 주봉·월봉·연봉으로 집계

### 4. Porto 매니저

- 사용자가 보고 있는 봉 주기를 기준으로 **다음 봉 종가 방향** 분석
- EMA, MACD, RSI, 거래량 신호, 볼린저 밴드, ATR 기반 점수 계산
- 현재 신호와 동일·유사했던 과거 구간의 상승·하락·보합 횟수 제공
- 기술 점수와 과거 상승 비율을 별도 지표로 구분
- 한국 주식은 NAVER·OpenDART, 미국 주식은 Alpha Vantage 뉴스 신호 활용
- 화면을 열면 `Porto의 한마디`를 자동 생성하고 추가 질문도 지원
- LLM 응답은 동일 분석에 대해 세션 캐시하여 불필요한 중복 호출 방지

> Porto 매니저의 방향은 선택한 봉의 다음 종가 방향에 대한 과거 패턴 추정입니다. 목표 가격이나 확정 수익률 예측이 아닙니다.

### 5. 포트폴리오 위험 시각화

- 별도 버튼 없이 저장 포트폴리오 화면에서 위험도를 자동 계산
- 최대 종목 비중, 상위 3종목 비중, HHI, 유효 종목 수로 집중 위험 측정
- 공통 일봉 구간으로 연환산 변동성, 최대 낙폭, Historical VaR 95% 계산
- 레버리지·인버스 추정 노출과 외화 노출 반영
- `안정형`, `균형형`, `공격형` 카드와 AI 한 줄 설명 제공

이 분류는 현재 보유 구성에서 관찰된 위험이며 법적 투자성향 또는 금융상품 적합성 판단이 아닙니다. 투자 목적, 기간, 소득, 부채, 생활자금과 손실 감내 수준은 별도 확인이 필요합니다.

### 6. 기업가치·재무제표

- 국내 종목: OpenDART 연간 공시
- 미국 종목: SEC EDGAR Company Facts
- 매출, 영업이익, 순이익, 자산, 부채, 자본, 영업현금흐름 시각화
- 현재가와 발행주식 수를 결합해 PER, PBR, PSR, ROE 계산
- 음수 또는 결측치로 의미가 없는 배수는 `NM` 또는 `자료 없음`으로 표시
- 조회 결과를 `fundamental_snapshots`에 upsert하여 재사용

### 7. 조건주문 안전장치

- SINGLE, OCO, OTO 조건주문 조회와 미리보기
- 실제 등록·수정·취소 기능은 환경변수로 기본 비활성화
- 주문 전 최종 확인 문구와 명시적 입력 필요
- 화면 세션에서 `clientOrderId`를 유지하여 중복 생성 위험 완화

## 서비스 흐름

```mermaid
flowchart LR
    U["사용자"] --> A["Streamlit UI"]
    A --> T["Toss Securities Open API"]
    A --> S["Porto Service Layer"]
    S --> D[("TiDB")]
    S --> N["NAVER · OpenDART · Alpha Vantage"]
    S --> F["SEC EDGAR"]
    S --> L["NVIDIA NIM"]

    T -->|"계좌 · 보유종목 · 시세 · 캔들"| S
    N -->|"뉴스 · 공시"| S
    F -->|"미국 재무제표"| S
    D -->|"저장 포트폴리오 · 캔들 · 재무"| S
    S -->|"규칙 기반 분석 + 설명"| A
```

### 저장 파이프라인

```text
app_users
  → brokerage_accounts
    → portfolio_snapshots
      → holding_snapshot_items
        → instruments
          ├─ candles
          ├─ price_snapshots
          ├─ news_articles
          └─ fundamental_snapshots
```

`instruments`와 시장 데이터는 동일 종목의 불필요한 중복을 줄이기 위해 공통 관리합니다. 오프라인 캔들 조회 시에는 `holding_snapshot_items → portfolio_snapshots → brokerage_accounts → user_id` 소유권을 SQL `EXISTS` 조건으로 검사합니다.

## 기술적 의사결정

### 규칙 기반 계산과 생성형 AI의 분리

```mermaid
flowchart LR
    C["캔들"] --> I["기술 지표 계산"]
    I --> B["유사 신호 백테스트"]
    W["뉴스 · 공시"] --> E["뉴스 심리 계산"]
    B --> J["구조화된 Manager Context"]
    E --> J
    J --> L["NVIDIA LLM"]
    L --> X["Porto의 한마디 · 추가 답변"]
```

점수와 과거 통계는 Python 코드가 결정합니다. LLM에는 개인정보와 API Key를 제외한 `porto.manager-context.v1` JSON만 전달하며, LLM은 계산값을 바꾸지 않고 사용자가 이해하기 쉽게 설명합니다. 뉴스 제목과 요약은 신뢰할 수 없는 외부 텍스트로 표시하여 프롬프트 명령으로 취급하지 않습니다.

### 데이터 저장 원칙

- 사용자 인증 비밀번호: `scrypt` 해시만 저장
- Toss Client ID·Client Secret: DB 미저장, 세션에서만 사용
- 포트폴리오: 계좌별 시점 스냅샷으로 보존
- 종목·캔들·뉴스·재무: 유일 키 기반 upsert
- DB 작업: 트랜잭션 단위 처리
- 오프라인 조회: 항상 로그인한 `user_id` 소유권 검증

## ERD

실제 `toss_manager/database.py`의 테이블과 주요 키를 기준으로 작성했습니다.

```mermaid
erDiagram
    APP_USERS {
        BIGINT user_id PK
        VARCHAR email UK
        VARCHAR password_hash
        VARCHAR display_name
        VARCHAR base_currency
        DATETIME created_at
    }

    BROKERAGE_ACCOUNTS {
        BIGINT account_id PK
        BIGINT user_id FK
        VARCHAR provider UK
        BIGINT toss_account_seq UK
        VARCHAR account_no_masked
        BOOLEAN is_active
    }

    PORTFOLIO_SNAPSHOTS {
        BIGINT snapshot_id PK
        BIGINT account_id FK
        DATETIME captured_at UK
        DECIMAL market_value_krw
        DECIMAL market_value_usd
        DECIMAL profit_loss_rate
        DECIMAL daily_profit_loss_rate
    }

    HOLDING_SNAPSHOT_ITEMS {
        BIGINT snapshot_id PK,FK
        BIGINT instrument_id PK,FK
        VARCHAR currency
        DECIMAL quantity
        DECIMAL last_price
        DECIMAL average_purchase_price
        DECIMAL market_value
        DECIMAL profit_loss_rate
    }

    INSTRUMENTS {
        BIGINT instrument_id PK
        VARCHAR symbol UK
        VARCHAR market UK
        VARCHAR market_country
        VARCHAR currency
        VARCHAR name
        VARCHAR english_name
        DECIMAL shares_outstanding
        DECIMAL leverage_factor
    }

    PRICE_SNAPSHOTS {
        BIGINT instrument_id PK,FK
        DATETIME captured_at PK
        DECIMAL last_price
        VARCHAR currency
    }

    CANDLES {
        BIGINT instrument_id PK,FK
        VARCHAR interval_code PK
        DATETIME candle_at PK
        DECIMAL open_price
        DECIMAL high_price
        DECIMAL low_price
        DECIMAL close_price
        DECIMAL volume
    }

    NEWS_ARTICLES {
        BIGINT news_id PK
        BIGINT instrument_id FK
        VARCHAR provider UK
        VARCHAR external_id UK
        VARCHAR content_type
        TEXT title
        DECIMAL sentiment_score
        DECIMAL relevance_score
        DATETIME published_at
    }

    NEWS_COLLECTION_STATE {
        BIGINT instrument_id PK,FK
        VARCHAR provider PK
        DATETIME last_success_at
    }

    FUNDAMENTAL_SNAPSHOTS {
        BIGINT fundamental_id PK
        BIGINT instrument_id FK
        VARCHAR provider UK
        INT fiscal_year UK
        VARCHAR statement_type
        DECIMAL revenue
        DECIMAL operating_income
        DECIMAL net_income
        DECIMAL assets
        DECIMAL liabilities
        DECIMAL equity
        DECIMAL operating_cash_flow
        DECIMAL market_price
        DECIMAL shares_outstanding
        DECIMAL market_cap
        DECIMAL per_ratio
        DECIMAL pbr_ratio
        DECIMAL psr_ratio
        DECIMAL roe_pct
        TEXT source_url
    }

    WATCHLIST_ITEMS {
        BIGINT user_id PK,FK
        BIGINT instrument_id PK,FK
        VARCHAR memo
        DECIMAL target_price
    }

    EXCHANGE_RATES {
        VARCHAR base_currency PK
        VARCHAR quote_currency PK
        DATETIME rate_at PK
        DECIMAL exchange_rate
    }

    APP_USERS ||--o{ BROKERAGE_ACCOUNTS : owns
    BROKERAGE_ACCOUNTS ||--o{ PORTFOLIO_SNAPSHOTS : captures
    PORTFOLIO_SNAPSHOTS ||--o{ HOLDING_SNAPSHOT_ITEMS : contains
    INSTRUMENTS ||--o{ HOLDING_SNAPSHOT_ITEMS : identifies
    INSTRUMENTS ||--o{ PRICE_SNAPSHOTS : records
    INSTRUMENTS ||--o{ CANDLES : has
    INSTRUMENTS ||--o{ NEWS_ARTICLES : has
    INSTRUMENTS ||--o{ NEWS_COLLECTION_STATE : tracks
    INSTRUMENTS ||--o{ FUNDAMENTAL_SNAPSHOTS : has
    APP_USERS ||--o{ WATCHLIST_ITEMS : owns
    INSTRUMENTS ||--o{ WATCHLIST_ITEMS : references
```

### 주요 유일 키

| 테이블 | 중복 방지 기준 |
|---|---|
| `app_users` | `email` |
| `brokerage_accounts` | `user_id + provider + toss_account_seq` |
| `instruments` | `symbol + market` |
| `portfolio_snapshots` | `account_id + captured_at` |
| `holding_snapshot_items` | `snapshot_id + instrument_id` |
| `candles` | `instrument_id + interval_code + candle_at` |
| `news_articles` | `provider + external_id + instrument_id` |
| `fundamental_snapshots` | `instrument_id + provider + fiscal_year` |

## 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend / App | Streamlit, Plotly |
| Language | Python 3.12+, pandas |
| Database | TiDB Cloud, SQLAlchemy, PyMySQL |
| Brokerage | Toss Securities Open API |
| News / Disclosure | NAVER Search API, OpenDART, Alpha Vantage |
| Fundamentals | OpenDART, SEC EDGAR Company Facts |
| Generative AI | NVIDIA NIM, Llama / Nemotron fallback |
| Test | unittest, pytest |
| Package management | uv |

## 프로젝트 구조

```text
TOSS_MANAGER/
├─ app.py                         # Streamlit 애플리케이션 조립
├─ main.py                        # 실행 진입점
├─ toss_manager/
│  ├─ analysis/                   # 지표, 신호 점수, 유사 패턴 백테스트
│  ├─ fundamentals/               # OpenDART·SEC 조회와 재무 저장
│  ├─ llm/                        # LLM 컨텍스트와 NVIDIA NIM 어댑터
│  ├─ news/                       # 뉴스 공급자, 저장소, 심리 계산
│  ├─ ui/                         # 인증, 차트, 매니저, 재무, 주문 화면
│  ├─ auth.py                     # 비밀번호 해시·검증
│  ├─ client.py                   # Toss Open API 클라이언트
│  ├─ conditional_orders.py       # 조건주문 검증과 payload 생성
│  ├─ database.py                 # TiDB 스키마 생성·검증
│  ├─ repository.py               # 포트폴리오·캔들 저장 계층
│  └─ risk_profile.py             # 포트폴리오 위험 특성 계산
└─ tests/                         # 단위·저장 계층 테스트
```

## 로컬 실행

### 1. 요구사항

- Python 3.12 이상
- [uv](https://docs.astral.sh/uv/)
- TiDB 또는 MySQL 호환 데이터베이스
- 토스증권 Open API Client ID / Client Secret

### 2. 설치

```bash
git clone <repository-url>
cd TOSS_MANAGER
uv sync
```

### 3. 환경변수

`.env.example`을 복사해 `.env`를 만들고 필요한 값을 입력합니다.

```dotenv
# TiDB: 전체 URL 또는 개별 DB_* 설정 중 하나
TIDB_DATABASE_URL=mysql+pymysql://user:password@host:4000/database

# 선택: 로그인 화면에서 직접 입력할 수도 있음
TOSS_CLIENT_ID=
TOSS_CLIENT_SECRET=
TOSS_API_BASE_URL=https://openapi.tossinvest.com

# 뉴스·공시·재무
NAVER_NEWS_CLIENT_ID=
NAVER_NEWS_CLIENT_SECRET=
OPENDART_API_KEY=
ALPHA_VANTAGE_API_KEY=
SEC_USER_AGENT="Porto operator@example.com"

# AI 설명
NVIDIA_API_KEY=

# 안전을 위해 기본 비활성화
TOSS_LIVE_CONDITIONAL_ORDERS_ENABLED=false
NEWS_REFRESH_SECONDS=60
```

`SEC_USER_AGENT`에는 회원가입 사용자의 이메일이 아니라 **Porto 운영자의 연락 가능한 이메일**을 사용합니다. SEC API Key가 아니라 SEC가 요청 애플리케이션을 식별하기 위한 값입니다.

### 4. 실행

```bash
uv run streamlit run main.py
```

앱 시작 시 TiDB 연결을 확인하고 필요한 테이블을 자동 생성합니다. 같은 이름의 기존 테이블이 호환되지 않는 구조라면 데이터를 임의로 변경하지 않고 오류를 표시합니다.

## 외부 서비스 설정

### Toss Securities

토스증권 WTS의 `설정 → Open API`에서 Porto 서버가 사용하는 공인 IPv4를 허용해야 합니다. Streamlit Community Cloud처럼 고정 outbound IP를 보장하지 않는 환경에서는 `IP address not allowed` 오류가 발생할 수 있으므로 고정 IP를 제공하는 서버 또는 프록시 구성이 필요합니다.

### NAVER

NAVER Developers에서 애플리케이션을 만들고 **검색 API의 뉴스 검색**을 선택합니다. Naver Cloud Platform의 공통 Access Key가 아니라 애플리케이션의 Client ID와 Client Secret을 사용합니다.

### OpenDART / SEC

- OpenDART 인증키는 `OPENDART_API_KEY`에 저장합니다.
- SEC는 별도 API Key 대신 `앱 이름 + 운영자 연락 이메일` 형태의 `SEC_USER_AGENT`가 필요합니다.

### NVIDIA NIM

`NVIDIA_API_KEY` 하나만 설정하면 Porto의 자동 한마디와 추가 질문 기능이 활성화됩니다. 기본 모델이 종료되거나 404/410을 반환하면 설정된 fallback 모델을 사용하며, 429 응답은 `Retry-After`에 따라 한 번 재시도합니다.

## 테스트

```bash
$env:PYTHONPATH=(Get-Location).Path
uv run --with pytest python -m pytest -q
```

현재 테스트 범위는 다음을 포함합니다.

- 사용자 인증과 비밀번호 검증
- 계좌·종목·캔들 upsert
- 포트폴리오 스냅샷 저장
- 사용자별 저장 캔들 접근 제한
- 5년 백필과 증분 수집 분기
- 기술 점수와 유사 신호 백테스트
- 뉴스 공급자와 심리 계산
- 조건주문 payload 및 안전 검증
- 재무제표 변환과 저장
- 포트폴리오 위험 특성
- LLM 컨텍스트와 NVIDIA API 예외 처리

```text
58 passed
```

## 안전과 한계

- Porto는 정보 제공 서비스이며 투자 권유 서비스가 아닙니다.
- 기술 분석은 과거 데이터 기반으로 다음 봉의 방향을 추정하며 미래 결과를 보장하지 않습니다.
- 뉴스 심리는 제목·요약 기반 규칙 점수이므로 기사 본문의 전체 맥락과 다를 수 있습니다.
- 재무 배수는 최신 연간 공시와 현재가를 결합하므로 결산 시점 차이가 존재합니다.
- 조건주문 실제 전송은 기본적으로 꺼져 있으며 충분한 검증 후에만 활성화해야 합니다.
- 시장 데이터와 외부 API의 지연, 호출 제한, 누락이 결과에 영향을 줄 수 있습니다.

## 향후 개선

- 사용자 격리 및 트랜잭션 rollback 통합 테스트 확대
- 고정 outbound IP 기반 배포 환경 구성
- 분기·연간 재무제표 비교와 성장률 시각화
- 포트폴리오 수익률 벤치마크와 자산배분 분석
- 뉴스 본문 라이선스 범위 내 고도화 및 이벤트 캘린더 결합
- 주문 체결 상태 추적과 멱등성 검증 강화
