"""Shared cohort/actual fact and date semantic invariants."""

from __future__ import annotations

from typing import Any


FACT_DATE_SEMANTICS = {
    "cohort": "install_cohort_date",
    "actual": "actual_event_date",
}


def date_semantics_for_fact_semantics(value: Any) -> str:
    fact_semantics = "" if value is None else str(value).strip().lower()
    return FACT_DATE_SEMANTICS.get(fact_semantics, "")


def validate_fact_date_semantics_pair(
    fact_semantics: Any,
    date_semantics: Any,
    *,
    allow_mixed: bool = False,
) -> None:
    fact_value = "" if fact_semantics is None else str(fact_semantics).strip().lower()
    date_value = "" if date_semantics is None else str(date_semantics).strip().lower()
    if not fact_value and not date_value:
        return
    if not fact_value or not date_value:
        raise ValueError("fact_semantics and date_semantics must be declared together")
    if allow_mixed and fact_value == "mixed" and date_value == "mixed":
        return
    expected = date_semantics_for_fact_semantics(fact_value)
    if not expected or date_value != expected:
        raise ValueError(
            f"fact/date semantics mismatch: {fact_value or 'missing'} / {date_value or 'missing'}"
        )


__all__ = [
    "FACT_DATE_SEMANTICS",
    "date_semantics_for_fact_semantics",
    "validate_fact_date_semantics_pair",
]
