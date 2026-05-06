from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config, DEFAULT_CONFIG
from .context_cards import context_card_for
from .endpoint_catalog import EndpointCatalog
from .api_templates import find_api_templates
from .query_analysis import QueryAnalysis
from .router import RoutingDecision
from .schema_index import SchemaIndex, normalize_name
from .sql_templates import find_sql_template


@dataclass
class MetadataSelector:
    schema_index: SchemaIndex
    endpoint_catalog: EndpointCatalog
    config: Config = DEFAULT_CONFIG

    def select(
        self,
        query: str,
        routing: RoutingDecision,
        *,
        strategy: str,
        query_id: str,
        broad_context: bool = False,
        analysis: QueryAnalysis | None = None,
    ) -> dict[str, Any]:
        selected_tables = routing.candidate_tables
        if broad_context:
            selected_tables = list(self.schema_index.tables)[:30]
        sql_template = None if broad_context else (analysis.sql_template if analysis else find_sql_template(query, self.schema_index))
        context_card = None if broad_context or self.config.disable_context_cards else context_card_for(analysis.lookup_path if analysis else None)
        relevant_tables = [item.name for item in analysis.relevance.tables[: self.config.relevance_top_k_tables]] if analysis and not broad_context else []
        if sql_template is not None:
            selected_tables = [table for table in sql_template.required_tables if table in self.schema_index.tables]
        elif context_card:
            selected_tables = [table for table in context_card.get("tables", []) if table in self.schema_index.tables] or selected_tables
        elif relevant_tables:
            selected_tables = relevant_tables
        selected_columns = {
            table: self._columns_for_strategy(
                table,
                broad_context,
                sql_template.required_columns.get(table) if sql_template else None,
                [item.name for item in analysis.relevance.columns.get(table, [])] if analysis else None,
            )
            for table in selected_tables
            if table in self.schema_index.tables
        }
        selected_apis = routing.candidate_apis
        if broad_context:
            selected_apis = self.endpoint_catalog.as_list()
        elif self.config.compact_metadata:
            api_templates = analysis.api_templates if analysis else find_api_templates(query, self.config)
            matched = []
            seen = set()
            for template in api_templates:
                endpoint = self.endpoint_catalog.match(template.method, template.path)
                if endpoint and endpoint.id not in seen:
                    seen.add(endpoint.id)
                    matched.append(compact_endpoint(endpoint.to_dict()))
            if matched:
                selected_apis = matched
            elif analysis and analysis.relevance.apis:
                selected_apis = [
                    compact_endpoint(endpoint.to_dict())
                    for item in analysis.relevance.apis[: self.config.relevance_top_k_apis]
                    if (endpoint := self.endpoint_catalog.by_id(item.name)) is not None
                ] or [compact_endpoint(api) for api in selected_apis]
            else:
                selected_apis = [compact_endpoint(api) for api in selected_apis]

        metadata = {
            "query_id": query_id,
            "query": query,
            "strategy": strategy,
            "route_type": routing.route_type,
            "domain_type": routing.domain_type,
            "selected_tables": selected_tables,
            "selected_columns": selected_columns,
            "selected_join_hints": self._select_join_hints(selected_tables, analysis, broad_context),
            "selected_apis": selected_apis,
            "known_example_patterns": self._load_relevant_gold_patterns(query, selected_apis, broad_context=broad_context),
            "constraints": self._constraints(broad_context),
            "answer_policy": self._answer_policy(broad_context),
        }
        if context_card:
            metadata["context_card"] = context_card
        if analysis and not broad_context:
            nlp = {
                "rewrites": analysis.normalization_rewrites[:3],
                "relevance": {
                    key: value[:2] if isinstance(value, list) else value
                    for key, value in analysis.relevance.compact(table_k=2, api_k=2).items()
                    if key in {"lookup_paths"}
                },
            }
            metadata["nlp_diagnostics"] = {key: value for key, value in nlp.items() if value not in ([], {}, "", None)}
        return metadata

    def _columns_for_strategy(
        self,
        table: str,
        broad_context: bool,
        required_columns: list[str] | None = None,
        relevant_columns: list[str] | None = None,
    ) -> list[str]:
        columns = self.schema_index.columns_for(table)
        if required_columns and self.config.compact_metadata:
            actual = []
            by_norm = {normalize_name(column): column for column in columns}
            for column in required_columns:
                match = by_norm.get(normalize_name(column))
                if match:
                    actual.append(match)
            if actual:
                return list(dict.fromkeys(actual))
        if relevant_columns and self.config.compact_metadata:
            actual = []
            by_norm = {normalize_name(column): column for column in columns}
            for column in relevant_columns:
                match = by_norm.get(normalize_name(column))
                if match:
                    actual.append(match)
            if actual:
                return list(dict.fromkeys(actual))[:16]
        if broad_context:
            return columns[:80]
        important = [
            column
            for column in columns
            if any(
                token in column.lower()
                for token in ["id", "name", "title", "status", "state", "time", "date", "count", "type"]
            )
        ]
        compact = important or columns[:16]
        return compact[:24]

    def _select_join_hints(
        self,
        selected_tables: list[str],
        analysis: QueryAnalysis | None,
        broad_context: bool,
    ) -> list[dict[str, Any]]:
        hints = self.schema_index.selected_join_hints(selected_tables)
        if broad_context:
            return hints[:30]
        if self.config.drop_one_join_hint and hints:
            hints = hints[1:]
        if analysis and analysis.relevance.join_hints:
            by_name = {
                f"{hint['left_table']}.{hint['left_column']}->{hint['right_table']}.{hint['right_column']}": hint
                for hint in hints
            }
            ranked = [by_name[item.name] for item in analysis.relevance.join_hints if item.name in by_name]
            if ranked:
                return ranked[: self.config.max_join_hints]
        return hints[: self.config.max_join_hints]

    def _load_relevant_gold_patterns(
        self, query: str, selected_apis: list[dict[str, Any]], *, broad_context: bool = False
    ) -> list[dict[str, Any]]:
        path = self.config.outputs_dir / "gold_api_patterns.json"
        if not path.exists():
            return []
        try:
            patterns = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        selected_paths = {api["path"] for api in selected_apis if "path" in api}
        lowered = query.lower()
        relevant = []
        for pattern in patterns:
            if pattern.get("path") in selected_paths or (
                broad_context
                and any(word in json.dumps(pattern).lower() for word in lowered.split()[:8])
            ):
                relevant.append(pattern if broad_context else compact_gold_pattern(pattern))
        return relevant[: (5 if broad_context else self.config.max_gold_patterns)]

    def _constraints(self, broad_context: bool) -> list[str]:
        if broad_context:
            return [
                "Use only known table names and columns.",
                "Use only endpoint catalog entries unless fallback mode is explicitly enabled.",
                "Validate SQL and API calls before execution.",
                "Prefer fewer tool calls when evidence is sufficient.",
            ]
        return ["Use validated SQL/API only.", "Prefer fewer tool calls when evidence is sufficient."]

    def _answer_policy(self, broad_context: bool) -> list[str]:
        if broad_context:
            return [
                "Answer from tool evidence only.",
                "Say not found when evidence is empty.",
                "Explicitly mention SQL/API disagreement when both are used.",
                "Do not invent IDs, counts, timestamps, states, or names.",
            ]
        return ["Answer from evidence only.", "Say not found/dry-run when evidence is empty."]

    def save(self, metadata: dict[str, Any], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "metadata.json"
        path.write_text(json.dumps(metadata, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return path


def compact_endpoint(endpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        key: endpoint[key]
        for key in ["id", "method", "path"]
        if key in endpoint
    }


def compact_gold_pattern(pattern: dict[str, Any]) -> dict[str, Any]:
    return {
        key: pattern[key]
        for key in ["method", "path", "params"]
        if key in pattern
    }
