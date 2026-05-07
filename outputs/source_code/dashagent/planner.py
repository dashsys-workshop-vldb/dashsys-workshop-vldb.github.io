from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .api_templates import find_api_templates
from .db import quote_ident
from .evidence_policy import API_SKIP, decide_api_need
from .endpoint_catalog import Endpoint
from .fast_paths import find_fast_path
from .plan_optimizer import optimize_plan_steps
from .query_analysis import QueryAnalysis
from .router import RoutingDecision
from .schema_index import SchemaIndex
from .sql_templates import SQLTemplate, find_sql_template


STRATEGIES = [
    "SQL_ONLY_BASELINE",
    "LLM_FREE_AGENT_BASELINE",
    "DETERMINISTIC_ROUTER_SELECTED_METADATA",
    "SQL_FIRST_API_VERIFY",
    "TEMPLATE_FIRST",
]

LLM_SQL_STRATEGIES = [
    "CANDIDATE_GUIDED_LLM_SQL",
    "FULL_SCHEMA_LLM_SQL",
    "LLM_SQL_FIRST_API_VERIFY",
]

ALL_STRATEGIES = STRATEGIES + LLM_SQL_STRATEGIES


@dataclass
class PlanStep:
    action: str
    purpose: str
    sql: str | None = None
    method: str | None = None
    url: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, Any] = field(default_factory=dict)
    allow_full_result: bool = False
    warnings: list[str] = field(default_factory=list)
    family: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            key: value
            for key, value in payload.items()
            if value not in (None, {}, [], "", False)
        }


@dataclass
class Plan:
    strategy: str
    rationale: str
    steps: list[PlanStep]
    optimizer_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "strategy": self.strategy,
            "rationale": self.rationale,
            "steps": [step.to_dict() for step in self.steps],
        }
        if self.optimizer_actions:
            payload["optimizer_actions"] = self.optimizer_actions
        return payload


class StrategyPlanner:
    def __init__(self, schema_index: SchemaIndex) -> None:
        self.schema_index = schema_index

    def create_plan(
        self,
        query: str,
        routing: RoutingDecision,
        metadata: dict[str, Any],
        strategy: str,
        analysis: QueryAnalysis | None = None,
    ) -> Plan:
        if strategy not in STRATEGIES:
            raise ValueError(f"Unknown strategy {strategy}. Expected one of {STRATEGIES}.")
        if strategy == "SQL_ONLY_BASELINE":
            return self._sql_only(query, routing, metadata, strategy)
        if strategy == "LLM_FREE_AGENT_BASELINE":
            return self._llm_free_baseline(query, routing, metadata, strategy)
        if strategy == "DETERMINISTIC_ROUTER_SELECTED_METADATA":
            return self._deterministic_selected(query, routing, metadata, strategy)
        if strategy == "SQL_FIRST_API_VERIFY":
            return self._sql_first_api_verify(query, routing, metadata, strategy, analysis)
        return self._template_first(query, routing, metadata, strategy, analysis)

    def _sql_only(
        self,
        query: str,
        routing: RoutingDecision,
        metadata: dict[str, Any],
        strategy: str,
    ) -> Plan:
        sql = self._build_sql(query, routing, metadata)
        steps = [
            PlanStep(
                action="sql",
                purpose="Answer from local snapshot using selected schema.",
                sql=sql,
                allow_full_result=asks_all_rows(query),
            )
        ] if sql else []
        return Plan(strategy, "SQL-only baseline avoids API calls unless no local table can be selected.", steps)

    def _llm_free_baseline(
        self,
        query: str,
        routing: RoutingDecision,
        metadata: dict[str, Any],
        strategy: str,
    ) -> Plan:
        steps: list[PlanStep] = []
        sql = self._build_sql(query, routing, metadata, broad=True)
        if sql:
            steps.append(
                PlanStep(
                    action="sql",
                    purpose="Broad-context baseline SQL attempt.",
                    sql=sql,
                    allow_full_result=asks_all_rows(query),
                )
            )
        for api_step in self._api_steps(query, routing, metadata, force=True)[:2]:
            api_step.purpose = "Broad-context baseline API probe."
            steps.append(api_step)
        return Plan(
            strategy,
            "Reproducible stand-in for a freer agent: broader metadata and extra API probes.",
            steps,
        )

    def _deterministic_selected(
        self,
        query: str,
        routing: RoutingDecision,
        metadata: dict[str, Any],
        strategy: str,
    ) -> Plan:
        steps: list[PlanStep] = []
        if routing.route_type in {"SQL_ONLY", "SQL_THEN_API", "SQL_AND_API_COMPARE", "API_THEN_SQL"}:
            sql = self._build_sql(query, routing, metadata)
            if sql:
                steps.append(
                    PlanStep(
                        action="sql",
                        purpose="Ground answer in selected local tables.",
                        sql=sql,
                        allow_full_result=asks_all_rows(query),
                    )
                )
        if routing.route_type in {"API_ONLY", "SQL_THEN_API", "SQL_AND_API_COMPARE", "API_THEN_SQL"}:
            steps.extend(self._api_steps(query, routing, metadata)[:1])
        return Plan(
            strategy,
            "Rule-based route with compact selected metadata and validated tool calls.",
            steps,
        )

    def _sql_first_api_verify(
        self,
        query: str,
        routing: RoutingDecision,
        metadata: dict[str, Any],
        strategy: str,
        analysis: QueryAnalysis | None = None,
    ) -> Plan:
        steps: list[PlanStep] = []
        planning_query = analysis.normalized_query if analysis else query
        fast_path = analysis.fast_path if analysis else find_fast_path(planning_query, self.schema_index)
        sql_template = analysis.sql_template if analysis else (fast_path.sql_template if fast_path else find_sql_template(planning_query, self.schema_index))
        sql = self._build_sql(planning_query, routing, metadata, sql_template=sql_template) if routing.route_type != "API_ONLY" else None
        if sql:
            steps.append(
                PlanStep(
                    action="sql",
                    purpose="Fast-path SQL grounding." if fast_path else "Ground names/IDs in local snapshot before API verification.",
                    sql=sql,
                    allow_full_result=sql_template.allow_full_result if sql_template else asks_all_rows(planning_query),
                    family=sql_template.family if sql_template else None,
                )
            )
        api_templates = analysis.api_templates if analysis else (fast_path.api_templates if fast_path else find_api_templates(planning_query))
        api_decision = analysis.api_need_decision if analysis else decide_api_need(planning_query, routing, sql_template, api_templates, strategy)
        if api_decision.mode != API_SKIP:
            steps.extend(
                self._api_steps(
                    planning_query,
                    routing,
                    metadata,
                    templates=api_templates,
                    allowed_families=api_decision.allowed_api_families,
                )
            )
        optimized = optimize_plan_steps(
            steps,
            strategy=strategy,
            route_type=routing.route_type,
            api_decision=api_decision,
        )
        steps = optimized.steps
        rationale = (
            strategy,
            f"SQL-first evidence policy: {api_decision.mode}. {api_decision.reason}",
            steps,
        )
        if fast_path:
            rationale = (rationale[0], rationale[1] + f" Fast path: {fast_path.family}.", rationale[2])
        if optimized.actions:
            rationale = (rationale[0], rationale[1] + " Optimized plan.", rationale[2])
        return Plan(*rationale, optimizer_actions=optimized.actions)

    def _template_first(
        self,
        query: str,
        routing: RoutingDecision,
        metadata: dict[str, Any],
        strategy: str,
        analysis: QueryAnalysis | None = None,
    ) -> Plan:
        planning_query = analysis.normalized_query if analysis else query
        template_sql = self._known_pattern_sql(planning_query, metadata)
        if template_sql:
            sql_template = analysis.sql_template if analysis else find_sql_template(planning_query, self.schema_index)
            steps = [
                PlanStep(
                    action="sql",
                    purpose="Known reusable query pattern.",
                    sql=template_sql,
                    allow_full_result=asks_all_rows(planning_query),
                    family=sql_template.family if sql_template else None,
                )
            ]
            api_templates = analysis.api_templates if analysis else find_api_templates(planning_query)
            api_decision = analysis.api_need_decision if analysis else decide_api_need(planning_query, routing, sql_template, api_templates, strategy)
            if api_decision.mode != API_SKIP:
                steps.extend(self._api_steps(planning_query, routing, metadata, templates=api_templates, allowed_families=api_decision.allowed_api_families))
            optimized = optimize_plan_steps(steps, strategy=strategy, route_type=routing.route_type, api_decision=api_decision)
            steps = optimized.steps
            rationale = "Template matched a reusable public-example-style pattern."
            if optimized.actions:
                rationale += " Optimized plan."
            return Plan(strategy, rationale, steps, optimized.actions)
        fallback = self._sql_first_api_verify(query, routing, metadata, "SQL_FIRST_API_VERIFY", analysis)
        return Plan(strategy, "No template matched; fell back to SQL-first API-verify plan.", fallback.steps)

    def _build_sql(
        self,
        query: str,
        routing: RoutingDecision,
        metadata: dict[str, Any],
        broad: bool = False,
        sql_template: SQLTemplate | None = None,
    ) -> str | None:
        if not broad:
            template = sql_template or find_sql_template(query, self.schema_index)
            if template is not None:
                return template.sql
        table = choose_table(query, routing.domain_type, metadata.get("selected_tables", []), self.schema_index)
        if table is None:
            return None
        columns = self.schema_index.columns_for(table)
        where_clauses = build_where_clauses(query, table, columns)
        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        allow_all = asks_all_rows(query)
        if asks_count(query):
            return f"SELECT COUNT(*) AS count FROM {quote_ident(table)}{where_sql}"
        selected = select_display_columns(query, columns, broad=broad)
        select_sql = ", ".join(quote_ident(column) for column in selected) if selected else "*"
        limit = "" if allow_all else " LIMIT 50"
        return f"SELECT {select_sql} FROM {quote_ident(table)}{where_sql}{limit}"

    def _api_steps(
        self,
        query: str,
        routing: RoutingDecision,
        metadata: dict[str, Any],
        force: bool = False,
        templates: list[Any] | None = None,
        allowed_families: list[str] | None = None,
    ) -> list[PlanStep]:
        raw_templates = templates if templates is not None else find_api_templates(query)
        allowed = set(allowed_families or [])
        templated_steps = [
            PlanStep(
                action="api",
                purpose=f"API parameter template: {template.family}.",
                method=template.method,
                url=template.path,
                params=template.params,
                warnings=template.warnings,
                family=template.family,
            )
            for template in raw_templates
            if ("{" not in template.path or force) and (not allowed or template.family in allowed)
        ]
        if templated_steps:
            return templated_steps
        if templates is not None:
            return []

        apis = metadata.get("selected_apis", [])
        if not apis:
            return []
        term = extract_search_term(query)
        steps: list[PlanStep] = []
        for api in apis:
            endpoint = endpoint_from_dict(api)
            if endpoint is None:
                continue
            url = endpoint.path
            schema_id = extract_schema_id(query)
            if endpoint.path_params:
                if "schema_id" in endpoint.path_params and schema_id:
                    url = url.replace("{schema_id}", schema_id)
                elif force:
                    continue
                else:
                    continue
            params = dict(endpoint.common_params)
            if term and not endpoint.path_params:
                params.setdefault("name", term)
            steps.append(
                PlanStep(
                    action="api",
                    purpose=f"Query Adobe endpoint {endpoint.id}.",
                    method=endpoint.method,
                    url=url,
                    params=params,
                )
            )
        return steps

    def _known_pattern_sql(self, query: str, metadata: dict[str, Any]) -> str | None:
        template = find_sql_template(query, self.schema_index)
        if template is not None:
            return template.sql
        lowered = query.lower()
        tables = metadata.get("selected_tables", [])
        table = choose_table(query, metadata.get("domain_type", "UNKNOWN"), tables, self.schema_index)
        if not table:
            return None
        columns = self.schema_index.columns_for(table)
        if asks_count(query):
            where = build_where_clauses(query, table, columns)
            where_sql = f" WHERE {' AND '.join(where)}" if where else ""
            return f"SELECT COUNT(*) AS count FROM {quote_ident(table)}{where_sql}"
        if ("status" in lowered or "published" in lowered or "inactive" in lowered) and any(
            "status" in c.lower() or "state" in c.lower() for c in columns
        ):
            return self._build_sql(query, RoutingDecision("SQL_ONLY", metadata.get("domain_type", "UNKNOWN"), 0.8, ""), metadata)
        return None


def endpoint_from_dict(payload: dict[str, Any]) -> Endpoint | None:
    try:
        return Endpoint(
            id=payload["id"],
            method=payload["method"],
            path=payload["path"],
            use_when=payload.get("use_when", ""),
            common_params=payload.get("common_params", {}),
            path_params=payload.get("path_params", []),
            examples=payload.get("examples", []),
            risk_notes=payload.get("risk_notes", []),
            domains=payload.get("domains", []),
        )
    except KeyError:
        return None


PREFERRED_TABLES = {
    "JOURNEY_CAMPAIGN": ["dim_campaign", "journey", "campaign"],
    "SEGMENT_AUDIENCE": ["dim_segment", "audience", "segment"],
    "DESTINATION_DATAFLOW": ["dim_target", "dim_connector", "flow", "target", "connector"],
    "DATASET_SCHEMA": ["dim_collection", "dim_blueprint", "dataset", "schema", "collection", "blueprint"],
    "PROPERTY_FIELD": ["dim_property", "property", "field"],
}


def choose_table(
    query: str,
    domain_type: str,
    selected_tables: list[str],
    schema_index: SchemaIndex,
) -> str | None:
    if not selected_tables:
        selected_tables = list(schema_index.tables)
    if not selected_tables:
        return None
    lowered_query = query.lower()
    preferences = PREFERRED_TABLES.get(domain_type, [])
    if "campaign" in lowered_query or "journey" in lowered_query:
        preferences = ["dim_campaign", "campaign", "journey", *preferences]
    if "segment" in lowered_query or "audience" in lowered_query:
        preferences = ["dim_segment", "segment", "audience", *preferences]
    if "connector" in lowered_query:
        preferences = ["dim_connector", "connector", *preferences]
    if "target" in lowered_query or "destination" in lowered_query:
        preferences = ["dim_target", "target", "destination", *preferences]
    if "property" in lowered_query or "field" in lowered_query:
        preferences = ["dim_property", "property", "field", *preferences]
    if "collection" in lowered_query or "dataset" in lowered_query:
        preferences = ["dim_collection", "collection", "dataset", *preferences]

    for preferred in preferences:
        for table in selected_tables:
            if table == preferred or preferred in table.lower():
                return table
    return selected_tables[0]


def select_display_columns(query: str, columns: list[str], broad: bool = False) -> list[str]:
    lowered_query = query.lower()
    priority_tokens = ["name", "title", "label", "status", "state", "id", "time", "date", "type", "count"]
    if any(word in lowered_query for word in ["status", "published", "inactive", "live", "failed", "succeeded"]):
        priority_tokens = ["name", "title", "status", "state", "lastdeployed", "published", "modified", "id"]
    selected = [
        column
        for column in columns
        if any(token in column.lower() for token in priority_tokens)
    ]
    if not selected:
        selected = columns[:8]
    limit = 16 if broad else 8
    return selected[:limit]


def build_where_clauses(query: str, table: str, columns: list[str]) -> list[str]:
    clauses: list[str] = []
    term = extract_search_term(query)
    name_column = first_column_containing(columns, ["name", "title", "label", "display"])
    if term and name_column:
        safe = term.replace("'", "''")
        clauses.append(f"LOWER(CAST({quote_ident(name_column)} AS VARCHAR)) LIKE LOWER('%{safe}%')")
    status_column = first_column_containing(columns, ["status", "state"])
    status_terms = [term for term in ["failed", "succeeded", "published", "inactive", "draft", "live"] if term in query.lower()]
    if status_column and status_terms:
        status = status_terms[0].replace("'", "''")
        clauses.append(f"LOWER(CAST({quote_ident(status_column)} AS VARCHAR)) LIKE LOWER('%{status}%')")
    return clauses


def first_column_containing(columns: list[str], tokens: list[str]) -> str | None:
    for token in tokens:
        for column in columns:
            if token in column.lower():
                return column
    return None


def extract_search_term(query: str) -> str | None:
    quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", query)
    for single, double in quoted:
        value = (single or double).strip()
        if value:
            return value
    match = re.search(r"\b(?:named|called|titled)\s+([A-Za-z0-9 _.-]{3,80})", query, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(" ?.!")
    return None


def extract_schema_id(query: str) -> str | None:
    match = re.search(r"\b([A-Za-z0-9_-]{12,}|https?://ns\.adobe\.com/[^\s]+)\b", query)
    return match.group(1) if match else None


def asks_count(query: str) -> bool:
    lowered = query.lower()
    return any(token in lowered for token in ["how many", "number of", "count", "total"])


def asks_live_state(query: str) -> bool:
    lowered = query.lower()
    return any(token in lowered for token in ["current", "live", "published", "inactive", "failed", "succeeded", "status", "platform", "sandbox", "api"])


def asks_all_rows(query: str) -> bool:
    lowered = query.lower()
    return any(token in lowered for token in ["all rows", "every row", "list all", "return all", "no row limit", "remove row limit", "every"])
