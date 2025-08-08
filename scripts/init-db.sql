-- scripts/init-db.sql
-- 初始化 TimescaleDB：启用扩展与基础表结构

-- 1. 启用 TimescaleDB 扩展（若已启用则忽略）
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 2. 普通表：tokens（项目静态信息）
CREATE TABLE IF NOT EXISTS tokens (
    id               UUID PRIMARY KEY,
    symbol           TEXT UNIQUE NOT NULL,
    name             TEXT,
    contract_address TEXT,
    chain            TEXT,
    github_repo_url  TEXT,
    website_url      TEXT,
    twitter_handle   TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ
);

-- 3. 超表原始结构（稍后在 create-hypertables.sql 中转换为 Hypertable）

-- 3.1 市场数据
CREATE TABLE IF NOT EXISTS market_data (
    time        TIMESTAMPTZ NOT NULL,
    token_id    UUID        NOT NULL,
    exchange    TEXT        NOT NULL,
    price       DOUBLE PRECISION NOT NULL,
    volume      DOUBLE PRECISION,
    bid         DOUBLE PRECISION,
    ask         DOUBLE PRECISION,
    spread      DOUBLE PRECISION,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_market_data_time   ON market_data(time DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_token  ON market_data(token_id);
CREATE INDEX IF NOT EXISTS idx_market_data_exch   ON market_data(exchange);

-- 3.2 链上事件
CREATE TABLE IF NOT EXISTS onchain_events (
    time          TIMESTAMPTZ NOT NULL,
    token_id      UUID,
    chain         TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    tx_hash       TEXT UNIQUE,
    block_number  BIGINT,
    from_address  TEXT,
    to_address    TEXT,
    value         DOUBLE PRECISION,
    gas_used      BIGINT,
    event_details JSONB
);
CREATE INDEX IF NOT EXISTS idx_onchain_time       ON onchain_events(time DESC);
CREATE INDEX IF NOT EXISTS idx_onchain_event_type ON onchain_events(event_type);
CREATE INDEX IF NOT EXISTS idx_onchain_chain      ON onchain_events(chain);

-- 3.3 Alpha 机会
CREATE TABLE IF NOT EXISTS alpha_opportunities (
    time               TIMESTAMPTZ NOT NULL,
    id                 UUID PRIMARY KEY,
    token_id           UUID,
    scout_type         TEXT NOT NULL,
    signal_type        TEXT NOT NULL,
    alpha_score        DOUBLE PRECISION NOT NULL,
    confidence         DOUBLE PRECISION,
    prediction_details JSONB,
    opportunity_data   JSONB,
    expires_at         TIMESTAMPTZ,
    executed           BOOLEAN DEFAULT FALSE,
    execution_result   JSONB
);
CREATE INDEX IF NOT EXISTS idx_alpha_time  ON alpha_opportunities(time DESC);
CREATE INDEX IF NOT EXISTS idx_alpha_score ON alpha_opportunities(alpha_score DESC);
CREATE INDEX IF NOT EXISTS idx_alpha_scout ON alpha_opportunities(scout_type);

-- 3.4 社交情绪
CREATE TABLE IF NOT EXISTS social_sentiment (
    time            TIMESTAMPTZ NOT NULL,
    token_id        UUID,
    platform        TEXT NOT NULL,
    mentions_count  INT,
    sentiment_score DOUBLE PRECISION,
    positive_count  INT,
    negative_count  INT,
    neutral_count   INT,
    influencer_mentions INT,
    trending_rank   INT,
    raw_data        JSONB
);
CREATE INDEX IF NOT EXISTS idx_sentiment_time     ON social_sentiment(time DESC);
CREATE INDEX IF NOT EXISTS idx_sentiment_platform ON social_sentiment(platform);

-- 3.5 开发者活动
CREATE TABLE IF NOT EXISTS developer_activity (
    time                TIMESTAMPTZ NOT NULL,
    token_id            UUID,
    github_repo         TEXT,
    commits_count       INT,
    pull_requests_open  INT,
    pull_requests_closed INT,
    issues_open         INT,
    issues_closed       INT,
    contributors_count  INT,
    stars_count         INT,
    forks_count         INT,
    activity_score      DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_dev_time  ON developer_activity(time DESC);
CREATE INDEX IF NOT EXISTS idx_dev_repo  ON developer_activity(github_repo);

