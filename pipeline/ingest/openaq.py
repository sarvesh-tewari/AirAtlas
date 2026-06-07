"""OpenAQ history fetch (API v3 + AWS S3 open-data archive).

Phase 3. Reads OPENAQ_API_KEY from the environment. Backfills multi-year history and
pulls daily deltas for the same CPCB Indian stations. Idempotent / self-healing:
gaps backfill on the next run.
"""
