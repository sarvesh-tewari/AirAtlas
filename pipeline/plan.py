"""Incremental-backfill planner.

The drip workflow backfills the dataset a few cities at a time so that every city shown to
users has complete history (complete-or-absent). Each fire processes the next batch of cities
that exist in the discovered universe but haven't been published yet.
"""

from __future__ import annotations

from collections.abc import Iterable


def next_batch(universe: Iterable[str], done: Iterable[str], n: int) -> list[str]:
    """The next up-to-`n` cities (sorted) present in `universe` but not yet in `done`.

    Sorted ordering makes successive drip fires advance deterministically.
    """
    done_set = set(done)
    return [c for c in sorted(set(universe)) if c not in done_set][:n]


def record_attempted(prev_attempted: Iterable[str], batch: Iterable[str]) -> list[str]:
    """Union this fire's batch into the attempted set (sorted, deduped).

    A city that was attempted but produced no data never enters the published city_list; tracking
    it as attempted is what stops the drip re-selecting it forever. Must union, never overwrite.
    """
    return sorted(set(prev_attempted) | set(batch))
