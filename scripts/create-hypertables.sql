-- scripts/create-hypertables.sql
-- 将普通表转换为 TimescaleDB 超表并添加管理策略

-- 1. 创建超表（如果尚未创建）
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);
SELECT create_hypertable('onchain_events', 'time', if_not_exists => TRUE);
SELECT create_hypertable('alpha_opportunities', 'time', if_not_exists => TRUE);
SELECT create_hypertable('social_sentiment', 'time', if_not_exists => TRUE);
SELECT create_hypertable('developer_activity', 'time', if_not_exists => TRUE);

-- 2. 设置 chunk 时间间隔（7 天）
SELECT set_chunk_time_interval('market_data', INTERVAL '7 days');
SELECT set_chunk_time_interval('onchain_events', INTERVAL '7 days');
SELECT set_chunk_time_interval('alpha_opportunities', INTERVAL '7 days');
SELECT set_chunk_time_interval('social_sentiment', INTERVAL '7 days');
SELECT set_chunk_time_interval('developer_activity', INTERVAL '7 days');

-- 3. 添加保留策略
SELECT add_retention_policy('market_data', INTERVAL '90 days');
SELECT add_retention_policy('onchain_events', INTERVAL '180 days');
SELECT add_retention_policy('alpha_opportunities', INTERVAL '365 days');
SELECT add_retention_policy('social_sentiment', INTERVAL '30 days');
SELECT add_retention_policy('developer_activity', INTERVAL '365 days');

-- 4. 创建连续聚合示例：1 分钟 OHLCV
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_1m
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 minute', time) AS bucket,
  token_id,
  exchange,
  FIRST(price, time) AS open,
  MAX(price) AS high,
  MIN(price) AS low,
  LAST(price, time) AS close,
  SUM(volume) AS volume,
  COUNT(*) AS tick_count
FROM market_data
GROUP BY bucket, token_id, exchange
WITH NO DATA;

SELECT add_continuous_aggregate_policy('market_data_1m',
  start_offset => INTERVAL '1 hour',
  end_offset => INTERVAL '1 minute',
  schedule_interval => INTERVAL '1 minute');

-- 5. 社交情绪小时聚合
CREATE MATERIALIZED VIEW IF NOT EXISTS sentiment_hourly
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 hour', time) AS bucket,
  token_id,
  platform,
  AVG(sentiment_score) AS avg_sentiment,
  SUM(mentions_count) AS total_mentions,
  MAX(trending_rank) AS best_rank
FROM social_sentiment
GROUP BY bucket, token_id, platform
WITH NO DATA;

SELECT add_continuous_aggregate_policy('sentiment_hourly',
  start_offset => INTERVAL '24 hours',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');
