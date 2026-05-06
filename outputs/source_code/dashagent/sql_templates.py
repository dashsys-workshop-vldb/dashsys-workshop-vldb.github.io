from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .db import quote_ident
from .schema_index import SchemaIndex, normalize_name


@dataclass(frozen=True)
class SQLTemplate:
    family: str
    sql: str
    required_tables: list[str]
    required_columns: dict[str, list[str]]
    allow_full_result: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "sql": self.sql,
            "required_tables": self.required_tables,
            "required_columns": self.required_columns,
            "allow_full_result": self.allow_full_result,
            "warnings": self.warnings,
        }


def find_sql_template(query: str, schema_index: SchemaIndex) -> SQLTemplate | None:
    lowered = query.lower()
    for builder in [
        journey_campaign_template,
        destination_export_template,
        segment_destination_template,
        connector_target_template,
        blueprint_collection_template,
        property_field_template,
        collection_created_by_template,
    ]:
        template = builder(query, lowered, schema_index)
        if template is not None:
            return template
    return None


def journey_campaign_template(query: str, lowered: str, schema: SchemaIndex) -> SQLTemplate | None:
    if not any(token in lowered for token in ["journey", "campaign"]):
        return None
    required = ["CAMPAIGNID", "NAME", "STATE", "UPDATEDTIME", "LASTDEPLOYEDTIME"]
    columns = columns_for(schema, "dim_campaign", required + ["STATUS"])
    if not has_all(columns, required):
        return None
    table = table_ref("dim_campaign")
    limit = limit_clause(query, default="50")
    term = quoted_term(query)

    if "inactive" in lowered:
        sql = (
            f"SELECT J.{quote_ident(columns['CAMPAIGNID'])} AS campaign_id, "
            f"J.{quote_ident(columns['NAME'])} AS campaign_name, "
            f"J.{quote_ident(columns['STATE'])} AS campaign_state, "
            f"J.{quote_ident(columns['UPDATEDTIME'])} AS updated_time "
            f"FROM {table} AS J "
            f"WHERE LOWER(CAST(J.{quote_ident(columns['STATE'])} AS VARCHAR)) NOT IN ('deployed', 'redeployed')"
            f"{limit}"
        )
        return SQLTemplate("journey_campaign_inactive", sql, ["dim_campaign"], {"dim_campaign": required})

    if "list" in lowered and "journey" in lowered:
        sql = (
            f"SELECT CAMPAIGN.{quote_ident(columns['NAME'])} AS CAMPAIGNNAME, "
            f"CAMPAIGN.{quote_ident(columns['CAMPAIGNID'])} AS CAMPAIGNID "
            f"FROM {table} AS CAMPAIGN"
            f"{limit_clause(query, default='10')}"
        )
        return SQLTemplate("journey_campaign_list", sql, ["dim_campaign"], {"dim_campaign": required})

    if "published" in lowered or "publish" in lowered:
        sql = (
            f"SELECT {quote_ident(columns['NAME'])} AS campaign_name, "
            f"{quote_ident(columns['LASTDEPLOYEDTIME'])} AS published_time "
            f"FROM {table}"
            f"{limit}"
        )
        return SQLTemplate("journey_campaign_published", sql, ["dim_campaign"], {"dim_campaign": required})

    return None


def segment_destination_template(query: str, lowered: str, schema: SchemaIndex) -> SQLTemplate | None:
    if not (
        any(token in lowered for token in ["segment", "audience"])
        and any(token in lowered for token in ["destination", "target"])
    ):
        return None
    required = {
        "dim_segment": ["SEGMENTID", "NAME", "TOTALMEMBERS", "CREATEDTIME", "UPDATEDTIME"],
        "hkg_br_segment_target": ["SEGMENTID", "TARGETID"],
        "dim_target": ["TARGETID", "DATAFLOWNAME", "NAME"],
    }
    resolved = resolve_required(schema, required)
    if resolved is None:
        return None
    if any(token in lowered for token in ["new destination", "new destinations", "last 3 months", "last three months", "mapped"]):
        time_required = {
            "dim_segment": ["SEGMENTID", "NAME"],
            "hkg_br_segment_target": ["SEGMENTID", "TARGETID"],
            "dim_target": ["TARGETID", "NAME", "CREATEDTIME"],
        }
        time_resolved = resolve_required(schema, time_required)
        if time_resolved is not None:
            a_time = time_resolved["dim_segment"]
            ad_time = time_resolved["hkg_br_segment_target"]
            d_time = time_resolved["dim_target"]
            sql = (
                f"SELECT DISTINCT A.{quote_ident(a_time['SEGMENTID'])} AS segment_id, "
                f"A.{quote_ident(a_time['NAME'])} AS segment_name, "
                f"D.{quote_ident(d_time['TARGETID'])} AS target_id, "
                f"D.{quote_ident(d_time['NAME'])} AS target_name "
                f"FROM {table_ref('dim_segment')} AS A "
                f"JOIN {table_ref('hkg_br_segment_target')} AS AD "
                f"ON A.{quote_ident(a_time['SEGMENTID'])} = AD.{quote_ident(ad_time['SEGMENTID'])} "
                f"JOIN {table_ref('dim_target')} AS D "
                f"ON AD.{quote_ident(ad_time['TARGETID'])} = D.{quote_ident(d_time['TARGETID'])} "
                f"WHERE D.{quote_ident(d_time['CREATEDTIME'])} >= DATEADD(MONTH, -3, CURRENT_DATE)"
                " LIMIT 3"
            )
            return SQLTemplate(
                "segment_new_destination_mapping",
                sql,
                list(time_required),
                {table: list(cols) for table, cols in time_required.items()},
            )
    term = quoted_term(query)
    where = ""
    if term:
        d = resolved["dim_target"]
        where = (
            f" WHERE D.{quote_ident(d['DATAFLOWNAME'])} = {sql_literal(term)} "
            f"OR D.{quote_ident(d['NAME'])} = {sql_literal(term)}"
        )
    a = resolved["dim_segment"]
    ad = resolved["hkg_br_segment_target"]
    d = resolved["dim_target"]
    sql = (
        f"SELECT A.{quote_ident(a['SEGMENTID'])} AS segment_id, "
        f"A.{quote_ident(a['NAME'])} AS segment_name, "
        f"A.{quote_ident(a['TOTALMEMBERS'])} AS total_profiles, "
        f"A.{quote_ident(a['CREATEDTIME'])} AS created_time, "
        f"A.{quote_ident(a['UPDATEDTIME'])} AS updated_time "
        f"FROM {table_ref('dim_segment')} AS A "
        f"JOIN {table_ref('hkg_br_segment_target')} AS AD "
        f"ON A.{quote_ident(a['SEGMENTID'])} = AD.{quote_ident(ad['SEGMENTID'])} "
        f"JOIN {table_ref('dim_target')} AS D "
        f"ON AD.{quote_ident(ad['TARGETID'])} = D.{quote_ident(d['TARGETID'])}"
        f"{where} "
        f"ORDER BY A.{quote_ident(a['NAME'])}"
        f"{limit_clause(query)}"
    )
    return SQLTemplate(
        "segment_destination_relationship",
        sql,
        list(required),
        {table: list(cols) for table, cols in required.items()},
        allow_full_result=asks_no_limit(query),
    )


def destination_export_template(query: str, lowered: str, schema: SchemaIndex) -> SQLTemplate | None:
    if "destination" not in lowered and "target" not in lowered:
        return None
    if not any(token in lowered for token in ["export", "sorted", "modified", "recent", "all destinations"]):
        return None
    required = {
        "dim_target": [
            "TARGETID",
            "DATAFLOWNAME",
            "NAME",
            "DESCRIPTION",
            "STATE",
            "CONNECTIONSPECID",
            "CREATEDTIME",
            "UPDATEDTIME",
            "INTERVAL",
            "FREQUENCY",
        ]
    }
    resolved = resolve_required(schema, required)
    if resolved is None:
        return None
    d = resolved["dim_target"]
    sql = (
        f"SELECT D.{quote_ident(d['TARGETID'])} AS target_id, "
        f"D.{quote_ident(d['DATAFLOWNAME'])} AS dataflow_name, "
        f"D.{quote_ident(d['NAME'])} AS target_name, "
        f"D.{quote_ident(d['DESCRIPTION'])}, "
        f"D.{quote_ident(d['STATE'])}, "
        f"D.{quote_ident(d['CONNECTIONSPECID'])} AS connection_spec_id, "
        f"D.{quote_ident(d['CREATEDTIME'])} AS created_time, "
        f"D.{quote_ident(d['UPDATEDTIME'])} AS modified, "
        f"D.{quote_ident(d['INTERVAL'])}, "
        f"D.{quote_ident(d['FREQUENCY'])} "
        f"FROM {table_ref('dim_target')} AS D "
        f"ORDER BY D.{quote_ident(d['UPDATEDTIME'])} DESC{destination_limit_clause(query)}"
    )
    return SQLTemplate("destination_export_recent", sql, ["dim_target"], required)


def connector_target_template(query: str, lowered: str, schema: SchemaIndex) -> SQLTemplate | None:
    if not any(token in lowered for token in ["connector", "source"]):
        return None
    if "destination" not in lowered and "target" not in lowered and "dataflow" not in lowered:
        return None
    required = {
        "dim_connector": ["DATAFLOWID", "DATAFLOWNAME", "NAME", "STATE", "UPDATEDTIME"],
        "dim_target": ["TARGETID", "DATAFLOWNAME", "NAME", "STATE", "UPDATEDTIME"],
    }
    resolved = resolve_required(schema, required)
    if resolved is None:
        return None
    s = resolved["dim_connector"]
    d = resolved["dim_target"]
    term = quoted_term(query)
    where = ""
    if term:
        where = (
            f" WHERE S.{quote_ident(s['DATAFLOWNAME'])} = {sql_literal(term)} "
            f"OR D.{quote_ident(d['DATAFLOWNAME'])} = {sql_literal(term)} "
            f"OR S.{quote_ident(s['NAME'])} = {sql_literal(term)} "
            f"OR D.{quote_ident(d['NAME'])} = {sql_literal(term)}"
        )
    sql = (
        f"SELECT S.{quote_ident(s['DATAFLOWID'])} AS source_dataflow_id, "
        f"S.{quote_ident(s['DATAFLOWNAME'])} AS source_dataflow_name, "
        f"D.{quote_ident(d['TARGETID'])} AS target_id, "
        f"D.{quote_ident(d['NAME'])} AS target_name, "
        f"D.{quote_ident(d['STATE'])} AS target_state "
        f"FROM {table_ref('dim_connector')} AS S "
        f"JOIN {table_ref('dim_target')} AS D "
        f"ON S.{quote_ident(s['NAME'])} = D.{quote_ident(d['NAME'])}"
        f"{where}"
        f"{limit_clause(query)}"
    )
    return SQLTemplate("connector_target_relationship", sql, list(required), {t: list(c) for t, c in required.items()})


def blueprint_collection_template(query: str, lowered: str, schema: SchemaIndex) -> SQLTemplate | None:
    if not any(token in lowered for token in ["schema", "blueprint", "dataset", "collection"]):
        return None
    required = {
        "dim_blueprint": ["BLUEPRINTID", "NAME", "CLASS", "ISPROFILEENABLED", "UPDATEDTIME"],
        "hkg_br_blueprint_collection": ["BLUEPRINTID", "COLLECTIONID"],
        "dim_collection": ["COLLECTIONID", "NAME", "ROWCOUNT", "UPDATEDTIME"],
    }
    resolved = resolve_required(schema, required)
    if resolved is None:
        return None
    b = resolved["dim_blueprint"]
    bc = resolved["hkg_br_blueprint_collection"]
    c = resolved["dim_collection"]
    term = quoted_term(query)

    if "experience event" in lowered and "profile" in lowered and asks_count(query):
        sql = (
            f"SELECT COUNT(DISTINCT B.{quote_ident(b['BLUEPRINTID'])}) AS num_experience_event_profile_enabled_blueprints "
            f"FROM {table_ref('dim_blueprint')} AS B "
            f"WHERE LOWER(B.{quote_ident(b['CLASS'])}) LIKE LOWER('%download%') "
            f"AND B.{quote_ident(b['ISPROFILEENABLED'])} = TRUE"
        )
        return SQLTemplate(
            "profile_enabled_experience_event_schema_count",
            sql,
            ["dim_blueprint"],
            {"dim_blueprint": ["BLUEPRINTID", "CLASS", "ISPROFILEENABLED"]},
        )

    if term and "detail" in lowered:
        property_required = {
            **required,
            "hkg_br_blueprint_property": ["BLUEPRINTID", "PROPERTY"],
        }
        detail_resolved = resolve_required(schema, property_required)
        if detail_resolved is not None:
            detail_blueprint = columns_for(
                schema,
                "dim_blueprint",
                ["BLUEPRINTID", "NAME", "CLASS", "ISPROFILEENABLED", "UPDATEDTIME", "REQUIREDFIELDS"],
            )
            bp = detail_resolved["hkg_br_blueprint_property"]
            required_field_select = ""
            required_field_group = ""
            if "REQUIREDFIELDS" in detail_blueprint:
                required_field_select = f"S.{quote_ident(detail_blueprint['REQUIREDFIELDS'])} AS required_fields, "
                required_field_group = f", S.{quote_ident(detail_blueprint['REQUIREDFIELDS'])}"
            sql = (
                f"SELECT S.{quote_ident(b['BLUEPRINTID'])} AS blueprint_id, "
                f"S.{quote_ident(b['NAME'])}, "
                f"S.{quote_ident(b['CLASS'])}, "
                f"S.{quote_ident(b['ISPROFILEENABLED'])}, "
                f"S.{quote_ident(b['UPDATEDTIME'])} AS updated_time, "
                f"{required_field_select}"
                f"COUNT(DISTINCT SD.{quote_ident(bc['COLLECTIONID'])}) AS collection_count, "
                f"COUNT(DISTINCT SA.{quote_ident(bp['PROPERTY'])}) AS property_count "
                f"FROM {table_ref('dim_blueprint')} AS S "
                f"LEFT JOIN {table_ref('hkg_br_blueprint_collection')} AS SD "
                f"ON S.{quote_ident(b['BLUEPRINTID'])} = SD.{quote_ident(bc['BLUEPRINTID'])} "
                f"LEFT JOIN {table_ref('hkg_br_blueprint_property')} AS SA "
                f"ON S.{quote_ident(b['BLUEPRINTID'])} = SA.{quote_ident(bp['BLUEPRINTID'])} "
                f"WHERE LOWER(S.{quote_ident(b['NAME'])}) = LOWER({sql_literal(term)}) "
                f"GROUP BY S.{quote_ident(b['BLUEPRINTID'])}, S.{quote_ident(b['NAME'])}, "
                f"S.{quote_ident(b['CLASS'])}, S.{quote_ident(b['ISPROFILEENABLED'])}, "
                f"S.{quote_ident(b['UPDATEDTIME'])}{required_field_group}"
                f"{limit_clause(query, default='3')}"
            )
            return SQLTemplate("schema_detail_counts", sql, list(property_required), {t: list(cols) for t, cols in property_required.items()})

    if asks_count(query) and "dataset" in lowered:
        if "same schema" in lowered:
            sql = (
                f"SELECT S.{quote_ident(b['BLUEPRINTID'])} AS blueprint_id, "
                f"S.{quote_ident(b['NAME'])} AS blueprint_name, "
                f"COUNT(DISTINCT DS.{quote_ident(bc['COLLECTIONID'])}) AS collection_count "
                f"FROM {table_ref('dim_collection')} AS D "
                f"JOIN {table_ref('hkg_br_blueprint_collection')} AS DS "
                f"ON D.{quote_ident(c['COLLECTIONID'])} = DS.{quote_ident(bc['COLLECTIONID'])} "
                f"JOIN {table_ref('dim_blueprint')} AS S "
                f"ON DS.{quote_ident(bc['BLUEPRINTID'])} = S.{quote_ident(b['BLUEPRINTID'])} "
                f"GROUP BY S.{quote_ident(b['BLUEPRINTID'])}, S.{quote_ident(b['NAME'])} "
                f"HAVING COUNT(DISTINCT DS.{quote_ident(bc['COLLECTIONID'])}) > 1"
            )
            return SQLTemplate("blueprint_collection_same_schema_count", sql, list(required), {t: list(cols) for t, cols in required.items()})
        sql = (
            f"SELECT B.{quote_ident(b['BLUEPRINTID'])} AS blueprint_id, "
            f"B.{quote_ident(b['NAME'])} AS blueprint_name, "
            f"COUNT(DISTINCT C.{quote_ident(c['COLLECTIONID'])}) AS collection_count "
            f"FROM {table_ref('dim_blueprint')} AS B "
            f"JOIN {table_ref('hkg_br_blueprint_collection')} AS BC "
            f"ON B.{quote_ident(b['BLUEPRINTID'])} = BC.{quote_ident(bc['BLUEPRINTID'])} "
            f"JOIN {table_ref('dim_collection')} AS C "
            f"ON BC.{quote_ident(bc['COLLECTIONID'])} = C.{quote_ident(c['COLLECTIONID'])} "
            f"GROUP BY B.{quote_ident(b['BLUEPRINTID'])}, B.{quote_ident(b['NAME'])} "
            f"ORDER BY collection_count DESC{limit_clause(query)}"
        )
        return SQLTemplate("blueprint_collection_count", sql, list(required), {t: list(cols) for t, cols in required.items()})

    if asks_count(query) and "schema" in lowered:
        sql = (
            f"SELECT COUNT(DISTINCT B.{quote_ident(b['BLUEPRINTID'])}) AS blueprint_count "
            f"FROM {table_ref('dim_blueprint')} AS B"
        )
        return SQLTemplate("schema_count", sql, ["dim_blueprint"], {"dim_blueprint": ["BLUEPRINTID"]})

    where = ""
    if term:
        where = f" WHERE B.{quote_ident(b['NAME'])} = {sql_literal(term)}"
    elif "recent" in lowered or "changes" in lowered:
        sql = (
            f"SELECT DISTINCT D.{quote_ident(c['COLLECTIONID'])} AS collection_id, "
            f"D.{quote_ident(c['NAME'])} AS collection_name, "
            f"D.{quote_ident(c['UPDATEDTIME'])} AS updated_time "
            f"FROM {table_ref('dim_collection')} AS D "
            f"WHERE D.{quote_ident(c['UPDATEDTIME'])} >= DATEADD(DAY, -90, CURRENT_DATE) "
            f"ORDER BY D.{quote_ident(c['UPDATEDTIME'])} DESC{limit_clause(query)}"
        )
        return SQLTemplate("recent_dataset_changes", sql, ["dim_collection"], {"dim_collection": ["COLLECTIONID", "NAME", "UPDATEDTIME"]})
    sql = (
        f"SELECT DISTINCT C.{quote_ident(c['COLLECTIONID'])} AS collection_id, "
        f"C.{quote_ident(c['NAME'])} AS collection_name "
        f"FROM {table_ref('hkg_br_blueprint_collection')} AS BC "
        f"JOIN {table_ref('dim_collection')} AS C "
        f"ON BC.{quote_ident(bc['COLLECTIONID'])} = C.{quote_ident(c['COLLECTIONID'])} "
        f"JOIN {table_ref('dim_blueprint')} AS B "
        f"ON BC.{quote_ident(bc['BLUEPRINTID'])} = B.{quote_ident(b['BLUEPRINTID'])}"
        f"{where}{limit_clause(query)}"
    )
    return SQLTemplate("blueprint_collection_list", sql, list(required), {t: list(cols) for t, cols in required.items()})


def property_field_template(query: str, lowered: str, schema: SchemaIndex) -> SQLTemplate | None:
    if not any(token in lowered for token in ["field", "property", "attribute"]):
        return None
    segment_name = quoted_term(query) or field_for_term(query)
    if "segment" in lowered or "audience" in lowered or segment_name:
        required = {
            "hkg_br_segment_property": ["SEGMENTID", "PROPERTY"],
            "dim_segment": ["SEGMENTID", "NAME"],
        }
        resolved = resolve_required(schema, required)
        if resolved is None:
            return None
        sp = resolved["hkg_br_segment_property"]
        s = resolved["dim_segment"]
        where = f" WHERE S.{quote_ident(s['NAME'])} = {sql_literal(segment_name)}" if segment_name else ""
        sql = (
            f"SELECT DISTINCT SP.{quote_ident(sp['PROPERTY'])} AS property_name, "
            f"S.{quote_ident(s['NAME'])} AS segment_name "
            f"FROM {table_ref('hkg_br_segment_property')} AS SP "
            f"JOIN {table_ref('dim_segment')} AS S "
            f"ON SP.{quote_ident(sp['SEGMENTID'])} = S.{quote_ident(s['SEGMENTID'])}"
            f"{where}{limit_clause(query, default='20')}"
        )
        return SQLTemplate("segment_property_fields", sql, list(required), {t: list(cols) for t, cols in required.items()})

    required = {
        "hkg_br_collection_property": ["COLLECTIONID", "PROPERTY"],
        "dim_collection": ["COLLECTIONID", "NAME"],
    }
    resolved = resolve_required(schema, required)
    if resolved is None:
        return None
    cp = resolved["hkg_br_collection_property"]
    c = resolved["dim_collection"]
    sql = (
        f"SELECT DISTINCT CP.{quote_ident(cp['PROPERTY'])} AS property_name, "
        f"C.{quote_ident(c['NAME'])} AS collection_name "
        f"FROM {table_ref('hkg_br_collection_property')} AS CP "
        f"JOIN {table_ref('dim_collection')} AS C "
        f"ON CP.{quote_ident(cp['COLLECTIONID'])} = C.{quote_ident(c['COLLECTIONID'])}"
        f"{limit_clause(query)}"
    )
    return SQLTemplate("collection_property_fields", sql, list(required), {t: list(cols) for t, cols in required.items()})


def collection_created_by_template(query: str, lowered: str, schema: SchemaIndex) -> SQLTemplate | None:
    if "created by" not in lowered and "created" not in lowered:
        return None
    if "download" not in lowered and not quoted_term(query):
        return None
    required = {"dim_collection": ["COLLECTIONID", "NAME", "CREATEDTIME", "CREATEDBY"]}
    resolved = resolve_required(schema, required)
    if resolved is None:
        return None
    c = resolved["dim_collection"]
    term = quoted_term(query) or "download"
    safe_term = term.replace("'", "''")
    sql = (
        f"SELECT DISTINCT C.{quote_ident(c['COLLECTIONID'])} AS collection_id, "
        f"C.{quote_ident(c['NAME'])} AS collection_name, "
        f"C.{quote_ident(c['CREATEDTIME'])} AS created_time "
        f"FROM {table_ref('dim_collection')} AS C "
        f"WHERE C.{quote_ident(c['CREATEDBY'])} ILIKE '%{safe_term}%'"
        f"{limit_clause(query, default='20')}"
    )
    return SQLTemplate("collection_created_by", sql, ["dim_collection"], required)


def resolve_required(schema: SchemaIndex, required: dict[str, list[str]]) -> dict[str, dict[str, str]] | None:
    resolved: dict[str, dict[str, str]] = {}
    for table, required_columns in required.items():
        if not schema.table_exists(table):
            return None
        table_columns = schema.columns_for(table)
        resolved[table] = {}
        for column in required_columns:
            actual = actual_column(table_columns, column)
            if actual is None:
                return None
            resolved[table][column] = actual
    return resolved


def columns_for(schema: SchemaIndex, table: str, wanted: list[str]) -> dict[str, str]:
    if not schema.table_exists(table):
        return {}
    columns = schema.columns_for(table)
    resolved = {}
    for column in wanted:
        actual = actual_column(columns, column)
        if actual:
            resolved[column] = actual
    return resolved


def actual_column(columns: list[str], wanted: str) -> str | None:
    target = normalize_name(wanted)
    for column in columns:
        if normalize_name(column) == target:
            return column
    return None


def has_all(resolved: dict[str, str], wanted: list[str]) -> bool:
    return all(column in resolved for column in wanted)


def quoted_term(query: str) -> str | None:
    matches = re.findall(r"'([^']+)'|\"([^\"]+)\"", query)
    for single, double in matches:
        value = (single or double).strip()
        if value:
            return value
    match = re.search(r"\bnamed\s+([A-Za-z0-9 _.:/-]{2,80})", query, flags=re.IGNORECASE)
    return match.group(1).strip(" .?!") if match else None


def field_for_term(query: str) -> str | None:
    match = re.search(r"\bfield\s+for\s+(.+)$", query, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip(" .?!")


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def table_ref(table: str) -> str:
    return quote_ident(table)


def asks_no_limit(query: str) -> bool:
    lowered = query.lower()
    return any(token in lowered for token in ["all", "no row limit", "remove row limit", "every"])


def limit_clause(query: str, default: str = "50") -> str:
    return "" if asks_no_limit(query) else f" LIMIT {default}"


def destination_limit_clause(query: str) -> str:
    lowered = query.lower()
    if any(token in lowered for token in ["no row limit", "remove row limit", "all rows", "every row", "return all rows"]):
        return ""
    return " LIMIT 50"


def asks_count(query: str) -> bool:
    lowered = re.sub(r"'[^']*'|\"[^\"]*\"", " ", query.lower())
    return any(token in lowered for token in ["how many", "count", "number of", "total"])
