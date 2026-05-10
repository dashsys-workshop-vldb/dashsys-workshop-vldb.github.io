from __future__ import annotations

from typing import Any

from .lookup_paths import LOOKUP_PATHS, LookupPath


ANSWER_POLICIES = {
    "journey_campaign": "Report publish/status evidence from dim_campaign; dry-run API is not confirmation.",
    "segment_destination": "Name audience/destination rows from SQL; only use API to verify live audience/flow evidence.",
    "destination_dataflow": "Use dim_target/dim_connector evidence first; live API validates platform state.",
    "schema_dataset": "Use blueprint/collection joins for local schema-dataset evidence; API may validate catalog/schema registry.",
    "property_field": "Answer from property bridge rows only; do not invent field descriptions.",
    "tags": "Tags are API evidence; report dry-run limits when credentials are unavailable.",
    "merge_policy": "Merge policies are API evidence; do not infer defaults from absent API payloads.",
    "observability": "Observability metrics require live API values; render returned date/value points only.",
    "batch": "Batch details/files are API evidence; keep dry-run answers explicit.",
    "audit": "Audit events are API evidence; SQL may ground related local entities.",
}


def context_card_for(path: LookupPath | None) -> dict[str, Any] | None:
    if path is None or path.family == "unknown":
        return None
    return {
        "family": path.family,
        "tables": path.tables,
        "join_path": path.join_path,
        "api_families": path.api_families,
        "required_ids": path.required_ids,
        "api_mode": path.api_mode,
        "answer_policy": ANSWER_POLICIES.get(path.family, "Answer only from SQL/API evidence."),
    }


def all_context_cards() -> dict[str, dict[str, Any]]:
    return {name: context_card_for(path) or {} for name, path in LOOKUP_PATHS.items()}
