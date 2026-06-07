"""Reconciliation seam: today = CPCB, history (<= yesterday) = OpenAQ.

Phase 4. Stitches the live snapshot and the historical series with no overlap, and
tags each row's source so the frontend can label it.
"""
