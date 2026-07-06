"""Illustrative sample - genericized, not production code.

A forensic-remediation pattern for fixing a set of suspect records safely:
  1. snapshot the current state (so any change is reversible),
  2. compute a diff of current versus corrected values,
  3. in dry-run, only REPORT the diff (touch nothing),
  4. on apply, write inside a transaction with a read-back check that
     rolls back the whole batch on any mismatch,
  5. adversarially verify by re-sampling N fixed records and asserting
     they truly changed.

Generic tables and fields only, no real record IDs or business rules.
"""

import random
from dataclasses import dataclass


@dataclass
class Fix:
    record_id: str
    field: str
    old_value: str
    new_value: str


def snapshot(conn, table, record_ids):
    """Capture a before-state for every record we intend to touch."""
    rows = conn.query(
        f"SELECT id, field, value FROM {table} WHERE id = ANY(%s)", [record_ids]
    )
    return {(r["id"], r["field"]): r["value"] for r in rows}


def compute_diff(before, corrected):
    """Only records whose corrected value actually differs become fixes."""
    fixes = []
    for (record_id, field), new_value in corrected.items():
        old_value = before.get((record_id, field))
        if old_value != new_value:
            fixes.append(Fix(record_id, field, old_value, new_value))
    return fixes


def remediate(conn, table, corrected, dry_run=True, verify_sample=5):
    record_ids = sorted({rid for (rid, _f) in corrected})
    before = snapshot(conn, table, record_ids)
    fixes = compute_diff(before, corrected)

    if dry_run:
        print(f"[dry-run] {len(fixes)} record(s) would change:")
        for fx in fixes:
            print(f"  {fx.record_id}.{fx.field}: {fx.old_value!r} -> {fx.new_value!r}")
        return {"applied": 0, "snapshot": before, "fixes": fixes}

    # Apply inside one transaction with a read-back guard.
    with conn.transaction() as tx:
        for fx in fixes:
            tx.execute(
                f"UPDATE {table} SET value = %s WHERE id = %s AND field = %s",
                [fx.new_value, fx.record_id, fx.field],
            )
            read_back = tx.query_one(
                f"SELECT value FROM {table} WHERE id = %s AND field = %s",
                [fx.record_id, fx.field],
            )
            if read_back["value"] != fx.new_value:
                # Any single mismatch rolls back the entire batch.
                raise RuntimeError(
                    f"read-back mismatch on {fx.record_id}.{fx.field}; rolling back"
                )

    adversarial_verify(conn, table, fixes, verify_sample)
    return {"applied": len(fixes), "snapshot": before, "fixes": fixes}


def adversarial_verify(conn, table, fixes, sample_size):
    """Re-read a random sample of fixed records and assert they truly changed."""
    if not fixes:
        return
    sample = random.sample(fixes, min(sample_size, len(fixes)))
    for fx in sample:
        current = conn.query_one(
            f"SELECT value FROM {table} WHERE id = %s AND field = %s",
            [fx.record_id, fx.field],
        )["value"]
        assert current == fx.new_value, f"{fx.record_id} did not take the fix"
        assert current != fx.old_value, f"{fx.record_id} still holds the old value"
    print(f"[verify] {len(sample)} sampled record(s) confirmed changed")
