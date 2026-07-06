# Illustrative sample - genericized, not production code.
"""
Incremental ETL with snapshot-before-mutate + dry-run safety.

Pattern: pull only rows changed since the last high-watermark, snapshot the
target rows before touching them, compute a diff, and in dry-run just report
it. On apply, write inside one transaction, verify with a read-back, and roll
back on any mismatch. Nothing mutates a live revenue table without a snapshot
it can restore from.

Warehouse + ETL architecture (generic):

  Sources                ETL workers (cron)            Warehouse (Postgres)
  ------------           -------------------           --------------------
  CRM API        --\                                   raw.*      (JSON payloads)
  Product API      >--->  extract (incremental)  --->  crm.*      (typed, joinable)
  Billing API    --/      transform                    billing.*
  External PG    ---->    load (upsert + snapshot)     common.*   (identity resolution)
                                                       meta.*     (watermarks, etl_runs)
                                                            |
                                                            v
                                                       Redash (self-service BI)
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

# Config is always read from the environment, never hardcoded.
DB_URL = os.environ["WAREHOUSE_DB_URL"]

TARGET_SCHEMA = "billing"
TARGET_TABLE = "orders"          # a live revenue table
PRIMARY_KEY = "order_id"
WATERMARK_COL = "updated_at"     # source-side change marker


@contextmanager
def get_conn():
    """Yield a connection that rolls back on error and always closes."""
    conn = psycopg2.connect(DB_URL)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_watermark(cur, source: str, stream: str) -> str:
    """Last successfully synced value for this source/stream, or epoch."""
    cur.execute(
        "SELECT watermark_value FROM meta.watermarks "
        "WHERE source = %s AND stream = %s",
        (source, stream),
    )
    row = cur.fetchone()
    return row[0] if row else "1970-01-01T00:00:00Z"


def extract_changed_rows(source_client, since: str) -> list[dict]:
    """Pull only records changed since the watermark (illustrative client)."""
    return source_client.list_records(updated_after=since)  # paginated upstream


def snapshot_target(cur, keys: list) -> str:
    """Copy the rows we are about to touch into a timestamped snapshot table."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snap = f"snapshots.{TARGET_TABLE}_{stamp}"
    cur.execute(f"CREATE TABLE {snap} (LIKE {TARGET_SCHEMA}.{TARGET_TABLE})")
    cur.execute(
        f"INSERT INTO {snap} "
        f"SELECT * FROM {TARGET_SCHEMA}.{TARGET_TABLE} "
        f"WHERE {PRIMARY_KEY} = ANY(%s)",
        (keys,),
    )
    return snap


def compute_diff(cur, rows: list[dict]) -> dict:
    """Split incoming rows into inserts vs updates against current state."""
    keys = [r[PRIMARY_KEY] for r in rows]
    cur.execute(
        f"SELECT {PRIMARY_KEY} FROM {TARGET_SCHEMA}.{TARGET_TABLE} "
        f"WHERE {PRIMARY_KEY} = ANY(%s)",
        (keys,),
    )
    existing = {r[0] for r in cur.fetchall()}
    inserts = [r for r in rows if r[PRIMARY_KEY] not in existing]
    updates = [r for r in rows if r[PRIMARY_KEY] in existing]
    return {"keys": keys, "inserts": inserts, "updates": updates}


def apply_upsert(cur, rows: list[dict]) -> None:
    """Idempotent write: insert new rows, update changed ones on conflict."""
    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != PRIMARY_KEY)
    sql = (
        f"INSERT INTO {TARGET_SCHEMA}.{TARGET_TABLE} ({', '.join(cols)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({PRIMARY_KEY}) DO UPDATE SET {updates}"
    )
    psycopg2.extras.execute_batch(
        cur, sql, [tuple(r[c] for c in cols) for r in rows], page_size=500
    )


def sync(source_client, source: str, stream: str, dry_run: bool = True) -> dict:
    """One incremental, snapshot-guarded sync of a live revenue table."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            since = get_watermark(cur, source, stream)
            rows = extract_changed_rows(source_client, since)
            if not rows:
                return {"changed": 0, "applied": False}

            diff = compute_diff(cur, rows)
            report = {
                "since": since,
                "inserts": len(diff["inserts"]),
                "updates": len(diff["updates"]),
            }

            if dry_run:
                # Report only. No snapshot, no writes, nothing committed.
                report["applied"] = False
                return report

            # Apply path: snapshot -> write -> read-back verify -> commit.
            snap = snapshot_target(cur, diff["keys"])
            apply_upsert(cur, rows)

            cur.execute(
                f"SELECT COUNT(*) FROM {TARGET_SCHEMA}.{TARGET_TABLE} "
                f"WHERE {PRIMARY_KEY} = ANY(%s)",
                (diff["keys"],),
            )
            present = cur.fetchone()[0]
            if present != len(diff["keys"]):
                # Read-back failed: abort and let the snapshot be the record
                # of pre-write state for a manual restore.
                conn.rollback()
                raise RuntimeError(
                    f"read-back mismatch: expected {len(diff['keys'])}, "
                    f"got {present}; snapshot at {snap}"
                )

            new_wm = max(r[WATERMARK_COL] for r in rows)
            cur.execute(
                "INSERT INTO meta.watermarks (source, stream, watermark_value, updated_at) "
                "VALUES (%s, %s, %s, NOW()) "
                "ON CONFLICT (source, stream) DO UPDATE SET "
                "watermark_value = EXCLUDED.watermark_value, updated_at = NOW()",
                (source, stream, new_wm),
            )
            conn.commit()
            report.update({"applied": True, "snapshot": snap, "watermark": new_wm})
            return report


if __name__ == "__main__":
    # Dry-run by default; pass DRY_RUN=false in the environment to apply.
    dry = os.environ.get("DRY_RUN", "true").lower() != "false"
    # `source_client` is any object exposing list_records(updated_after=...).
    result = sync(source_client=None, source="billing", stream="orders", dry_run=dry)
    print(result)
