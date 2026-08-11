"""Synthetic fixtures for the financial-crime investigation swarm (fincrime_router.py).

A compact, self-contained dataset mirroring a typical KYC/AML alert-investigation narrative — no
real customer, institution, or individual is represented. Each dict below stands in for one
source system a real investigation would touch. Modeled after (not copied from) the "hsbc-fincrime"
reference demo's dataset shape (D1-D9 fixtures) described in the plan; all entity names, IDs, and
narrative details here are original.
"""

from __future__ import annotations

__all__ = [
    "ALERT",
    "CUSTOMER",
    "KYC_DOCUMENTS",
    "UBO_CHAIN",
    "WORLDCHECK_HITS",
    "SANCTIONS_HITS",
    "PEP_HITS",
    "ADVERSE_MEDIA",
    "CASE_HISTORY",
    "ENTITY_LINKS",
    "TRANSACTIONS",
    "COUNTERPARTIES",
    "ACTIVITY_PROFILE",
    "RM_DIRECTORY",
]

ALERT = {
    "id": "ALRT-2026-0708",
    "trigger": "Unusual cross-border trade-finance activity",
    "customer": "Meridian Trade Holdings Ltd",
}

CUSTOMER = {
    "name": "Meridian Trade Holdings Ltd",
    "incorporated": "United Kingdom, 2016",
    "relationship_since": "2019",
    "segment": "Trade finance — commodities intermediary",
    "declared_corridor": "UK ↔ Singapore",
    "current_risk_rating": "Medium (last reviewed 2024-11-02, OVERDUE)",
}

KYC_DOCUMENTS = [
    {"doc": "Certificate of Incorporation", "status": "on file", "date": "2016-03-11"},
    {"doc": "Ownership declaration", "status": "on file, unverified", "date": "2019-06-04"},
    {"doc": "Annual KYC refresh", "status": "OVERDUE by 14 months", "date": "2024-11-02"},
]

UBO_CHAIN = {
    "customer": "Meridian Trade Holdings Ltd",
    "chain": [
        "Meridian Trade Holdings Ltd (UK)",
        "→ Ashworth Capital Partners Ltd (Cayman Islands, holding layer)",
        "→ Northgate Commercial SA (British Virgin Islands, holding layer)",
        "→ Ultimate Beneficial Owner: Dimitri Kovalenko — 76% ownership",
    ],
    "note": "Two offshore holding layers obscure the UBO from the customer's own KYC file.",
}

WORLDCHECK_HITS = [
    {
        "name_screened": "Dimitri Kovalenko",
        "match": "Dimitri Kovalenko",
        "match_score": 0.97,
        "category": "PEP",
        "detail": "Former Deputy Minister for Trade, 2014-2019.",
    },
    {
        "name_screened": "Dimitri Kovalenko",
        "match": "Dimitri Kovalenkov",
        "match_score": 0.71,
        "category": "Sanctions watchlist",
        "detail": "Different DOB (1958 vs 1971) and jurisdiction (Belarus vs the UBO's UK residency).",
    },
]

SANCTIONS_HITS = [
    {
        "name_screened": "Dimitri Kovalenko",
        "list": "Consolidated sanctions list",
        "match": "Dimitri Kovalenkov",
        "assessment": "Likely false positive — DOB and jurisdiction mismatch against the UBO.",
    }
]

PEP_HITS = [
    {
        "name_screened": "Dimitri Kovalenko",
        "status": "CONFIRMED PEP",
        "role": "Former Deputy Minister for Trade (2014-2019)",
        "domestic_or_foreign": "Foreign PEP",
    }
]

ADVERSE_MEDIA = [
    {
        "name_screened": "Dimitri Kovalenko",
        "headline": "Local reporting (2021) links former ministry officials to shell-company networks",
        "relevance": "medium",
    }
]

CASE_HISTORY = [
    {
        "case_id": "CASE-2026-00417",
        "subject": "Northbridge Maritime Logistics Ltd",
        "status": "OPEN",
        "type": "Trade-based money laundering (TBML)",
        "note": "Shares a director with the UBO of Meridian Trade Holdings Ltd.",
    },
    {
        "case_id": "CASE-2025-00298",
        "subject": "Meridian Trade Holdings Ltd",
        "status": "CLOSED — no action",
        "type": "Prior monitoring alert, 2025-02",
        "note": "Discounted: one-off large payment, invoice matched.",
    },
]

ENTITY_LINKS = [
    {
        "entity_a": "Dimitri Kovalenko",
        "entity_b": "Northbridge Maritime Logistics Ltd",
        "relationship": "Shared director (appointed 2020-05)",
        "linked_case": "CASE-2026-00417",
    }
]

TRANSACTIONS = [
    {"id": "TXN-1001", "date": "2026-05-02", "counterparty": "Ashworth Capital Partners Ltd", "amount_usd": 480_000, "direction": "out", "note": "Trade finance settlement"},
    {"id": "TXN-1002", "date": "2026-05-09", "counterparty": "Northgate Commercial SA", "amount_usd": 475_000, "direction": "in", "note": "Returned within 7 days"},
    {"id": "TXN-1003", "date": "2026-05-15", "counterparty": "Silverline Trading FZE", "amount_usd": 460_000, "direction": "out", "note": "Same corridor, new counterparty"},
    {"id": "TXN-1004", "date": "2026-05-22", "counterparty": "Ashworth Capital Partners Ltd", "amount_usd": 458_000, "direction": "in", "note": "Returned within 7 days"},
    {"id": "TXN-1005", "date": "2026-06-03", "counterparty": "Regional Cargo Distributors Ltd", "amount_usd": 62_000, "direction": "out", "note": "Baseline trade activity, matches declared profile"},
    {"id": "TXN-1006", "date": "2026-06-11", "counterparty": "Coastal Freight & Co", "amount_usd": 58_500, "direction": "out", "note": "Baseline trade activity, matches declared profile"},
    {"id": "TXN-1007", "date": "2026-06-19", "counterparty": "Northgate Commercial SA", "amount_usd": 501_000, "direction": "out", "note": "GB-CY corridor, undeclared"},
    {"id": "TXN-1008", "date": "2026-06-27", "counterparty": "Silverline Trading FZE", "amount_usd": 497_000, "direction": "in", "note": "Returned within 8 days"},
]

COUNTERPARTIES = [
    {"name": "Ashworth Capital Partners Ltd", "jurisdiction": "Cayman Islands", "role": "UBO holding layer"},
    {"name": "Northgate Commercial SA", "jurisdiction": "British Virgin Islands / Cyprus", "role": "UBO holding layer"},
    {"name": "Silverline Trading FZE", "jurisdiction": "UAE", "role": "Shell counterparty, first seen 2026-05"},
    {"name": "Regional Cargo Distributors Ltd", "jurisdiction": "Singapore", "role": "Declared, baseline trading partner"},
    {"name": "Coastal Freight & Co", "jurisdiction": "Singapore", "role": "Declared, baseline trading partner"},
]

ACTIVITY_PROFILE = {
    "declared_corridor": "UK ↔ Singapore",
    "declared_monthly_volume_usd": 150_000,
    "actual_corridor_observed": "UK ↔ Singapore (baseline) plus an undeclared UK ↔ Cyprus corridor",
    "actual_monthly_volume_usd": 890_000,
    "gap": "The GB-CY corridor (Northgate Commercial SA, Silverline Trading FZE) is not declared "
    "in the customer's activity profile, and no source-of-funds evidence is on file for it.",
}

RM_DIRECTORY = {
    "customer": "Meridian Trade Holdings Ltd",
    "relationship_manager": "Priya Chandrasekaran",
    "team": "Trade & Working Capital, London",
    "email": "priya.chandrasekaran@example-bank.test",
}
