"""Data fetching helpers with caching for Streamlit."""

from __future__ import annotations

import streamlit as st
from api_client import ChironAPIClient


@st.cache_data(ttl=30, show_spinner=False)
def fetch_eleves_with_syntheses(
    _client: ChironAPIClient, classe_id: str, trimestre: int
) -> list[dict]:
    """Fetch students with syntheses, cached for 30 seconds.

    Note: _client prefix tells Streamlit not to hash this argument.

    Args:
        _client: API client instance.
        classe_id: Class identifier.
        trimestre: Trimester number.

    Returns:
        List of students with synthesis status.
    """
    return _client.get_eleves_with_syntheses(classe_id, trimestre)


def get_status_counts(eleves_data: list[dict]) -> dict:
    """Calculate status counts from eleves data.

    Args:
        eleves_data: List from fetch_eleves_with_syntheses.

    Returns:
        Dict with total, with_synthese, validated, pending, missing counts.
    """
    total = len(eleves_data)
    with_synthese = sum(1 for e in eleves_data if e.get("has_synthese"))
    validated = sum(1 for e in eleves_data if e.get("synthese_status") == "validated")

    return {
        "total": total,
        "with_synthese": with_synthese,
        "validated": validated,
        "pending": with_synthese - validated,
        "missing": total - with_synthese,
    }


def clear_eleves_cache() -> None:
    """Clear the eleves cache to force refresh."""
    fetch_eleves_with_syntheses.clear()
