# scripts/sqlite_to_timescale.py
"""一键迁移旧 SQLite 数据到 TimescaleDB。

步骤：
1. 读取环境变量：
   SQLITE_PATH (默认 data/crypto_scout.db)
   DATABASE_URL (TimescaleDB async URL)
2. 连接 SQLite (同步)、TimescaleDB (asyncpg)
3. 逐行读取旧表数据，转换/批量插入对应 TimescaleDB 表。

本脚本主要迁移 market_data / onchain_events / alpha_opportunities 三张核心表，
其余表可按需补充。
"""

import asyncio
import os
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sqlite_to_timescale")

SQLITE_PATH = os.getenv("SQLITE_PATH", "data/crypto_scout.db")
TSDB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://crypto_user:SecureDBPass123!@localhost:5432/crypto_scout",
)
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))

CREATE_TEMP_TABLE = """CREATE TEMP TABLE _tmp_import AS SELECT * FROM {table} WHERE 0;"""

TABLES = [
    ("market_data", [
        "time", "token_id", "exchange", "price", "volume",
        "bid", "ask", "spread", "open", "high", "low", "close"
    ]),
    ("onchain_events", [
        "time", "token_id", "chain", "event_type", "tx_hash",
        "block_number", "from_address", "to_address", "value", "gas_used", "event_details"
    ]),
    ("alpha_opportunities", [
        "time", "id", "token_id", "scout_type", "signal_type",
        "alpha_score", "confidence", "prediction_details", "opportunity_data",
        "expires_at", "executed", "execution_result"
    ]),
]


def fetch_sqlite_rows(conn: sqlite3.Connection, table: str, columns: List[str]):
    cursor = conn.cursor()
    cursor.execute(f"SELECT {', '.join(columns)} FROM {table}")
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        yield rows


async def migrate_table(pool: asyncpg.Pool, conn_sqlite: sqlite3.Connection, table: str, columns: List[str]):
    col_names = ", ".join(columns)
    placeholder = ", ".join([f"${i+1}" for i in range(len(columns))])
    insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholder}) ON CONFLICT DO NOTHING"

    total = 0
    async with pool.acquire() as conn_pg:
        for batch in fetch_sqlite_rows(conn_sqlite, table, columns):
            await conn_pg.executemany(insert_sql, batch)
            total += len(batch)
            if total % 5000 == 0:
                logger.info(f"{table}: migrated {total} rows")
    logger.info(f"{table}: migration complete, total {total} rows")


async def main():
    if not os.path.exists(SQLITE_PATH):
        logger.error("SQLite file not found: %s", SQLITE_PATH)
        return

    conn_sqlite = sqlite3.connect(SQLITE_PATH)
    pool = await asyncpg.create_pool(TSDB_URL, min_size=1, max_size=10)

    try:
        for table, columns in TABLES:
            logger.info("Migrating table %s", table)
            await migrate_table(pool, conn_sqlite, table, columns)
    finally:
        await pool.close()
        conn_sqlite.close()

    logger.info("✅ SQLite → TimescaleDB migration finished")

if __name__ == "__main__":
    asyncio.run(main())

