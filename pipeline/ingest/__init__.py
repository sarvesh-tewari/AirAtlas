"""Ingestion: fetch raw data from CPCB (live), OpenAQ (history), Open-Meteo (weather).

Each module caches responses and respects each standard's averaging windows
where relevant.
"""
