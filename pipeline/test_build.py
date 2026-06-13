"""Tests for meta-assembly helpers in build.py."""

import build


def test_merge_centroids_fills_prior_cities_not_in_this_run():
    # This run only discovered Mumbai's stations, so `centroids` lacks Delhi. Delhi was published
    # by an earlier batch, so its centroid lives in the prior cities.json — recover it, or Delhi's
    # map marker loses its lat/lon when meta is rebuilt from the full on-disk union.
    centroids = {"Mumbai": (19.07, 72.87)}
    prior_index = [
        {"city": "Delhi", "lat": 28.61, "lon": 77.20},
        {"city": "Mumbai", "lat": 0.0, "lon": 0.0},  # stale; this run's value must win
    ]
    merged = build.merge_centroids(centroids, prior_index)
    assert merged["Delhi"] == (28.61, 77.20)        # recovered from prior
    assert merged["Mumbai"] == (19.07, 72.87)       # this run's fresh value preserved
