from __future__ import annotations

from dataclasses import dataclass

from .api_templates import APITemplate, find_api_templates
from .schema_index import SchemaIndex
from .sql_templates import SQLTemplate, find_sql_template


FAST_PATH_MARKERS = {
    "batch",
    "dataset",
    "destination",
    "failed dataflow",
    "journey",
    "merge polic",
    "observability",
    "schema",
    "segment definition",
    "segment job",
    "tag",
    "timeseries.",
    "ingestion record",
}


@dataclass(frozen=True)
class FastPath:
    family: str
    sql_template: SQLTemplate | None
    api_templates: list[APITemplate]

    def to_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "sql_template": self.sql_template.to_dict() if self.sql_template else None,
            "api_templates": [template.to_dict() for template in self.api_templates],
        }


def find_fast_path(query: str, schema_index: SchemaIndex) -> FastPath | None:
    lowered = query.lower()
    if not any(marker in lowered for marker in FAST_PATH_MARKERS):
        return None
    sql_template = find_sql_template(query, schema_index)
    api_templates = find_api_templates(query)
    if not sql_template and not api_templates:
        return None
    family_parts = []
    if sql_template:
        family_parts.append(sql_template.family)
    family_parts.extend(template.family for template in api_templates[:2])
    return FastPath(
        family="+".join(family_parts) if family_parts else "api_only",
        sql_template=sql_template,
        api_templates=api_templates,
    )
