"""Tests for the incremental-backfill batch planner."""

import plan


def test_next_batch_returns_sorted_undone_cities():
    universe = {"Delhi", "Mumbai", "Chennai", "Kolkata", "Pune"}
    done = {"Delhi", "Mumbai"}
    # Sorted for determinism so successive drip fires advance predictably; done cities skipped.
    assert plan.next_batch(universe, done, 2) == ["Chennai", "Kolkata"]


def test_next_batch_empty_when_all_done():
    universe = {"Delhi", "Mumbai"}
    assert plan.next_batch(universe, {"Delhi", "Mumbai"}, 5) == []


def test_next_batch_caps_at_remaining():
    universe = {"Delhi", "Mumbai", "Chennai"}
    # n larger than what's left returns only the remaining undone cities.
    assert plan.next_batch(universe, {"Delhi"}, 10) == ["Chennai", "Mumbai"]


def test_record_attempted_unions_with_prior_not_overwrites():
    # Each fire must ADD its batch to the attempted set, not replace it — otherwise a city that
    # was attempted but yielded no data (so it never got published) would be retried forever,
    # stalling the drip. Sorted + deduped.
    prev = ["Indore", "Delhi"]
    batch = ["Lucknow", "Delhi"]  # Delhi overlaps; must dedupe
    assert plan.record_attempted(prev, batch) == ["Delhi", "Indore", "Lucknow"]


def test_record_attempted_from_empty():
    assert plan.record_attempted([], ["Patna", "Agra"]) == ["Agra", "Patna"]
