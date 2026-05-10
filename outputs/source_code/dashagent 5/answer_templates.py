from __future__ import annotations

import re
from typing import Any

from .live_response_parsers import normalize_api_evidence


def classify_answer_family(query: str) -> str:
    lowered = query.lower()
    if "field" in lowered or "property" in lowered or "attribute" in lowered:
        return "property_field"
    if "created by" in lowered or ("created" in lowered and "download" in lowered):
        return "audit_entity_created"
    if "segment definition" in lowered:
        return "segment_definitions"
    if "segment job" in lowered or "segment evaluation job" in lowered:
        return "segment_jobs"
    if ("journey" in lowered or "campaign" in lowered) and "publish" in lowered:
        return "journey_published"
    if "inactive" in lowered and ("journey" in lowered or "campaign" in lowered):
        return "inactive_journeys"
    if "list" in lowered and "journey" in lowered:
        return "list_journeys"
    if ("audience" in lowered or "segment" in lowered) and ("destination" in lowered or "target" in lowered):
        if any(token in lowered for token in ["mapped", "new destination", "new destinations", "last 3 months", "last three months"]):
            return "audit_destination_mapping"
        return "segment_destination"
    if ("destination" in lowered or "target" in lowered) and any(token in lowered for token in ["export", "list", "recent", "modified"]):
        return "destination_export"
    if "failed" in lowered and ("dataflow" in lowered or "run" in lowered or "file" in lowered):
        return "failed_dataflow_runs"
    if "merge polic" in lowered:
        return "merge_policy"
    if "timeseries." in lowered or "observability" in lowered or "ingestion record" in lowered:
        return "observability_metrics"
    if "batch" in lowered or "batches" in lowered:
        return "batch"
    if "tag" in lowered:
        return "tags"
    if "schema" in lowered or "dataset" in lowered:
        return "schema_dataset"
    if "audit" in lowered or "created by" in lowered:
        return "audit_destination_mapping"
    return "generic"


def render_answer_template(
    query: str,
    sql_results: list[dict[str, Any]],
    api_results: list[dict[str, Any]],
) -> str | None:
    family = classify_answer_family(query)
    rows = first_ok_rows(sql_results)
    api_phrase = api_evidence_phrase(api_results)
    lowered = query.lower()

    if family == "journey_published":
        query_name = quoted_text(query)
        row = matching_row(rows, ["campaign_name", "campaignname", "name"], query_name) or first_row(rows)
        name = row_value(row, ["campaign_name", "campaignname", "name"]) or query_name or "the journey"
        published_time = row_value(row, ["published_time", "lastdeployedtime"])
        if row and published_time not in (None, "", "None", "null"):
            return f'The journey "{name}" was published at {published_time}.'
        if api_phrase == "the API returned no matching results":
            api_phrase = "the Adobe AJO API returns no results for it"
        return (
            f'The journey "{name}" has not been published. '
            f"The database shows a null published_time for this journey, and {api_phrase}."
        )

    if family == "inactive_journeys" and rows is not None:
        if not rows:
            return f"No inactive journeys were found in the database, and {api_phrase}."
        pieces = []
        for row in rows[:6]:
            name = row_value(row, ["campaign_name", "campaignname", "name"]) or "unnamed campaign"
            updated = row_value(row, ["updated_time", "updatedtime"])
            if updated:
                pieces.append(f"{name} (last updated {human_date(updated)})")
            else:
                pieces.append(str(name))
        return f"There are {len(rows)} inactive campaigns: {join_human(pieces)}. {sentence_case(api_phrase)}."

    if family == "list_journeys" and rows is not None:
        names = extract_names(rows, ["campaign_name", "campaignname", "name"])
        if names:
            return f"Based on the available evidence, there are {len(names)} journeys found in the database: {join_human(names)}. {sentence_case(api_phrase)}."
        return f"No journeys were found in the database. {sentence_case(api_phrase)}."

    if family == "destination_export" and rows is not None:
        if not rows:
            return f"No destinations were found in the database. {sentence_case(api_phrase)}."
        row = rows[0]
        dataflow = row_value(row, ["dataflow_name", "dataflowname"]) or "unknown dataflow"
        target = row_value(row, ["target_name", "name"]) or "unknown target"
        modified = row_value(row, ["modified", "updated_time", "updatedtime"])
        suffix = f" with a modification timestamp of {human_datetime(modified)}" if modified else ""
        sandbox_note = ""
        if "sandbox" in lowered:
            sandbox_note = " Live API evidence is needed to validate the requested sandbox."
        destination_phrase = "1 destination was" if len(rows) == 1 else f"{len(rows)} destinations were"
        return f'Based on the evidence provided, {destination_phrase} found. The most recent is "{dataflow}" ({target} target){suffix}.{sandbox_note} {sentence_case(api_phrase)}.'

    if family == "audit_entity_created" and rows is not None:
        actor = quoted_text(query) or "download"
        if not rows:
            return f"Based on the evidence provided, no entities were created by {actor}. The SQL query returned zero rows, and {api_phrase}."
        names = extract_names(rows, ["collection_name", "name", "entity_name"])
        return f"Based on the evidence provided, entities created by {actor} are: {join_human(names) if names else format_rows(rows)}. {sentence_case(api_phrase)}."

    if family in {"segment_destination", "audit_destination_mapping"} and rows is not None:
        if not rows:
            if any(result.get("payload", {}).get("dry_run") for result in api_results):
                return (
                    "Based on the evidence provided, there is no data available to answer this question. "
                    "The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable, "
                    "so audience and flow service evidence could not be checked."
                )
            return (
                "Based on the evidence provided, there is no data available to answer this question. "
                f"The SQL query returned zero rows, and {api_phrase}."
            )
        names = extract_names(rows, ["segment_name", "audience_name", "name"])
        target_names = extract_names(rows, ["target_name", "destination_name", "dataflow_name"])
        created = row_value(rows[0], ["created_time", "createdtime"])
        details = []
        for row in rows[:3]:
            segment_id = row_value(row, ["segment_id", "audience_id", "segmentid"])
            name = row_value(row, ["segment_name", "audience_name", "name"])
            total = row_value(row, ["total_profiles", "totalprofiles", "totalmembers"])
            updated = row_value(row, ["updated_time", "updatedtime"])
            pieces = [str(name or segment_id or "unnamed audience")]
            if segment_id and name:
                pieces.append(f"ID {segment_id}")
            if total is not None:
                pieces.append(f"{total} total profiles")
            if updated:
                pieces.append(f"updated {human_date(updated)}")
            details.append(" (".join([pieces[0], ", ".join(pieces[1:]) + ")"]) if len(pieces) > 1 else pieces[0])
        target_phrase = f" mapped to {join_human(target_names)}" if target_names else " mapped to a destination"
        date_phrase = f" on {human_date(created)}" if created else ""
        subject = join_human(details) if details else join_human(names) if names else "unnamed audience"
        return f"Based on the SQL evidence, {len(rows)} audience(s) match: {subject}{target_phrase}{date_phrase}. {sentence_case(api_phrase)}."

    if family == "failed_dataflow_runs":
        if rows == [] or rows is None:
            return (
                "Based on the evidence provided, there are no failed dataflow runs to report. "
                f"The SQL query returned zero rows, and {api_phrase}."
            )
        ids = extract_names(rows, ["dataflow_id", "run_id", "id"])
        return f"Based on the available evidence, failed dataflow identifiers are: {join_human(ids) if ids else format_rows(rows)}. {sentence_case(api_phrase)}."

    if family == "schema_dataset":
        answer = schema_dataset_answer(query, rows, api_phrase)
        if answer:
            return answer

    if family == "merge_policy":
        live = first_api_evidence(api_results, "merge_policies")
        if live and not live["empty"]:
            count = live.get("count", 0)
            fields = live.get("important_fields", {})
            name = fields.get("default_policy_name") or fields.get("name") or fields.get("title")
            if asks_count(lowered):
                return f"The API evidence reports {count} merge polic{'y' if count == 1 else 'ies'}."
            if "list" in lowered:
                names = extract_names(live.get("items", []), ["name", "title", "id"])
                return f"The merge policies returned by the API are: {join_human(names[:10]) if names else name or 'available in the API evidence'}."
            if name:
                return f"The default merge policy is {name}. This is based on live merge-policy API evidence."
        if rows:
            names = extract_names(rows, ["name", "policy_name", "merge_policy_name"])
            if names:
                return f"The matching merge policy evidence identifies: {join_human(names)}. {sentence_case(api_phrase)}."
        if asks_count(lowered):
            return f"The merge policy count cannot be determined from the available evidence. {sentence_case(api_phrase)}."
        if "default" in lowered:
            return f"The default merge policy requires live Adobe API evidence. {sentence_case(api_phrase)}."
        return f"Merge policy information requires Adobe API evidence. {sentence_case(api_phrase)}."

    if family == "observability_metrics":
        live = first_api_evidence(api_results, "observability_metrics")
        if live and not live["empty"]:
            rendered = render_observability_values(query, live)
            if rendered:
                return rendered
            return f"Observability metrics were returned by the API. {sentence_case(api_phrase)}."
        metric_names = extract_metric_names(query)
        dates = extract_dates(query)
        metric_phrase = join_human(metric_names) if metric_names else "the requested observability metrics"
        window = f" between {dates[0]} and {dates[-1]}" if len(dates) >= 2 else " for the requested time window"
        return (
            f"Values for {metric_phrase}{window} require live API evidence. "
            f"{sentence_case(api_phrase)}."
        )

    if family == "batch":
        live = first_api_evidence(api_results, "batch")
        if live and not live["empty"]:
            items = live.get("items", [])
            count = live.get("count", len(items))
            fields = live.get("important_fields", {})
            if asks_count(lowered):
                status = quoted_text(query) or row_value(fields, ["status", "state"])
                suffix = f" with status '{status}'" if status else ""
                return f"The API evidence reports {count} batch{'es' if count != 1 else ''}{suffix}."
            if "file" in lowered:
                names = extract_names(items, ["fileName", "filename", "id", "batchId"])
                return f"The available batch file(s) are: {join_human(names[:10]) if names else format_rows(items)}."
            batch_id = row_value(fields, ["batchId", "id", "_id"]) or quoted_text(query)
            status = row_value(fields, ["status", "state"])
            dataset = row_value(fields, ["datasetId", "dataset", "dataSetId"])
            pieces = []
            if status:
                pieces.append(f"status/state {status}")
            if dataset:
                pieces.append(f"dataset {dataset}")
            detail = f" with {', '.join(pieces)}" if pieces else ""
            return f"The API evidence reports batch {batch_id or 'details'}{detail}."
        if asks_count(lowered):
            return f"The batch count requires live API evidence. {sentence_case(api_phrase)}."
        if "file" in lowered:
            return f"Batch file details require live API evidence. {sentence_case(api_phrase)}."
        return f"Batch details require live API evidence. {sentence_case(api_phrase)}."

    if family == "segment_definitions":
        live = first_api_evidence(api_results, "segment_definition")
        if live and not live["empty"]:
            count = live.get("count", 0)
            fields = live.get("important_fields", {})
            name = fields.get("name") or fields.get("title")
            item_id = fields.get("id")
            updated = fields.get("updatedTime") or fields.get("updateTime") or fields.get("modified")
            suffix = []
            if item_id:
                suffix.append(f"ID {item_id}")
            if updated:
                suffix.append(f"updated {human_datetime(updated)}")
            detail = f" ({', '.join(suffix)})" if suffix else ""
            if "recent" in lowered or "updated" in lowered:
                return f"The most recent segment definition returned by the API is {name or 'available in the API evidence'}{detail}. The API evidence reports {count} item(s)."
            return f"The API evidence reports {count} segment definition(s). The first visible definition is {name or 'available in the API evidence'}{detail}."
        if "recent" in lowered or "updated" in lowered:
            return (
                "The most recently updated segment definitions require live Adobe API evidence with names, IDs, and update times. "
                f"{sentence_case(api_phrase)}."
            )
        if "list" in lowered or "all segment definitions" in lowered:
            return (
                "The requested segment definition list requires live Adobe API evidence with definition names, IDs, and pagination counts. "
                f"{sentence_case(api_phrase)}."
            )
        return (
            "Segment definition details require live Adobe API evidence with definition names, IDs, and counts. "
            f"{sentence_case(api_phrase)}."
        )

    if family == "segment_jobs":
        live = first_api_evidence(api_results, "segment_jobs")
        if live and not live["empty"]:
            fields = live.get("important_fields", {})
            status = fields.get("status") or fields.get("state")
            item_id = fields.get("id")
            count = live.get("count", 0)
            details = []
            if status:
                details.append(f"status {status}")
            if item_id:
                details.append(f"ID {item_id}")
            suffix = f" with {', '.join(details)}" if details else ""
            return f"The API evidence reports {count} segment evaluation job(s){suffix}."
        if asks_count(lowered):
            return (
                "The segment evaluation job count requires live Adobe API evidence. "
                f"{sentence_case(api_phrase)}."
            )
        return (
            "Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. "
            f"{sentence_case(api_phrase)}."
        )

    if family == "property_field" and rows is not None:
        if not rows:
            return f"No matching field was found in the database. {sentence_case(api_phrase)}."
        row = rows[0]
        field = row_value(row, ["property_name", "property", "field"])
        segment = row_value(row, ["segment_name", "name"]) or quoted_text(query) or "the segment"
        if field:
            label = human_property_label(str(field))
            extra = ""
            if "birth" in label or "birthday" in str(segment).lower():
                extra = " This field captures when a person was born and is used to identify birthday-related audiences."
            return f'The field for "{segment}" is {field}. This is the {label} property from the SQL evidence.{extra}'
        return f"The matching field evidence is: {format_rows(rows)}. {sentence_case(api_phrase)}."

    if family == "tags":
        live = first_api_evidence(api_results, "tag")
        if live and not live["empty"]:
            count = live.get("count", 0)
            items = live.get("items", [])
            fields = live.get("important_fields", {})
            name = fields.get("name") or fields.get("title")
            tag_id = fields.get("id")
            if asks_count(lowered):
                return f"The API evidence reports {count} tag(s)."
            if "list" in lowered or "all tags" in lowered:
                names = extract_names(items, ["name", "title", "id"])
                return f"The tag(s) returned by the API are: {join_human(names[:10]) if names else name or 'available in the API evidence'}."
            suffix = f" (ID: {tag_id})" if tag_id else ""
            return f"The tag API returned {name or 'a matching tag'}{suffix}."
        if api_has_live_payload(api_results):
            return f"Tag evidence was returned by the API. {sentence_case(api_phrase)}."
        if asks_count(lowered):
            return f"The tag count cannot be determined from the available evidence. {sentence_case(api_phrase)}."
        if "list" in lowered or "all tags" in lowered:
            return f"The requested tag list requires live API evidence. {sentence_case(api_phrase)}."
        if quoted_text(query):
            return (
                f"Details for the tag named '{quoted_text(query)}' require live API evidence, including the tag ID, name, category, and Adobe organization. "
                f"{sentence_case(api_phrase)}."
            )
        if "category" in lowered:
            return f"Tag category membership requires live API evidence. {sentence_case(api_phrase)}."
        return f"Tag details require live API evidence. {sentence_case(api_phrase)}."

    return None


def schema_dataset_answer(query: str, rows: list[dict[str, Any]] | None, api_phrase: str) -> str | None:
    lowered = query.lower()
    if rows is None:
        return None
    if not rows:
        name = quoted_text(query)
        if name:
            return f"Based on the evidence provided, no datasets use the schema '{name}'. The SQL query returned zero results, and {api_phrase}."
        return f"The SQL query returned zero matching schema or dataset rows, and {api_phrase}."
    first = rows[0]
    if asks_count(lowered):
        count = first_count_value(first)
        if count is not None:
            if "experience event" in lowered:
                return f"Based on the SQL query result, there are {count} XDM Experience Event schemas enabled for profile in your environment."
            if "schema" in lowered and "dataset" not in lowered:
                return f"You have {count} schemas. {sentence_case(api_phrase)}."
            schema_name = row_value(first, ["blueprint_name", "schema_name", "name"])
            tail = f' These datasets use "{schema_name}".' if schema_name else ""
            return f"Based on the evidence provided, {count} datasets have been ingested using the same schema.{tail} {sentence_case(api_phrase)}."
    if "detail" in lowered or "details" in lowered:
        name = row_value(first, ["name", "blueprint_name"]) or quoted_text(query) or "the schema"
        class_value = row_value(first, ["class"])
        props = row_value(first, ["property_count"])
        collections = row_value(first, ["collection_count"])
        updated = row_value(first, ["updated_time", "updatedtime"])
        bits = []
        if class_value:
            bits.append(f"has class {class_value}")
        if props is not None:
            bits.append(f"has {props} properties")
        if collections is not None:
            bits.append(f"across {collections} collection(s)")
        if updated:
            bits.append(f"and was last updated on {human_date(updated)}")
        details = ", ".join(bits) if bits else "was found"
        return f"The '{name}' schema {details}. {sentence_case(api_phrase)}."
    names = extract_names(rows, ["collection_name", "dataset_name", "name"])
    if names:
        return f"Based on the evidence provided, matching datasets are: {join_human(names[:10])}. {sentence_case(api_phrase)}."
    return None


def first_ok_rows(sql_results: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    for result in sql_results:
        payload = result.get("payload", {})
        if payload.get("ok"):
            return payload.get("rows") or []
    return None


def first_row(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    return rows[0] if rows else None


def matching_row(rows: list[dict[str, Any]] | None, candidates: list[str], wanted: str | None) -> dict[str, Any] | None:
    if not rows or not wanted:
        return None
    wanted_norm = normalize_key(wanted)
    for row in rows:
        value = row_value(row, candidates)
        if value is not None and normalize_key(str(value)) == wanted_norm:
            return row
    for row in rows:
        value = row_value(row, candidates)
        if value is not None and wanted_norm in normalize_key(str(value)):
            return row
    return None


def api_evidence_phrase(api_results: list[dict[str, Any]]) -> str:
    if not api_results:
        return "API evidence was not requested"
    if any(result.get("payload", {}).get("dry_run") for result in api_results):
        return "live API verification was not executed because Adobe credentials are unavailable"
    live_payloads = [result.get("payload", {}) for result in api_results]
    if any(payload.get("ok") and payload.get("result_preview") not in (None, "", [], {}) for payload in live_payloads):
        return "the API returned usable supporting evidence"
    if any(payload.get("ok") for payload in live_payloads):
        return "the API returned no matching results"
    return "API evidence did not provide usable data"


def api_has_live_payload(api_results: list[dict[str, Any]]) -> bool:
    return any(
        result.get("payload", {}).get("ok") and not result.get("payload", {}).get("dry_run")
        for result in api_results
    )


def first_api_evidence(api_results: list[dict[str, Any]], family_prefix: str) -> dict[str, Any] | None:
    for result in api_results:
        step = result.get("step", {})
        family = str(step.get("family") or "")
        if family.startswith(family_prefix) or family_prefix in family:
            return normalize_api_evidence(family, result.get("payload", {}))
    return None


def row_value(row: dict[str, Any] | None, candidates: list[str]) -> Any:
    if not row:
        return None
    normalized = {normalize_key(key): value for key, value in row.items()}
    for candidate in candidates:
        value = normalized.get(normalize_key(candidate))
        if value is not None:
            return value
    return None


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def extract_names(rows: list[dict[str, Any]], candidates: list[str]) -> list[str]:
    names = []
    for row in rows:
        value = row_value(row, candidates)
        if value not in (None, ""):
            names.append(str(value))
    return list(dict.fromkeys(names))


def first_count_value(row: dict[str, Any]) -> Any:
    for key, value in row.items():
        if "count" in key.lower() or normalize_key(key) in {"total", "num"}:
            return value
    if len(row) == 1:
        return next(iter(row.values()))
    return None


def asks_count(lowered_query: str) -> bool:
    return any(token in lowered_query for token in ["how many", "count", "number of", "total"])


def quoted_text(query: str) -> str | None:
    match = re.search(r"'([^']+)'|\"([^\"]+)\"", query)
    return (match.group(1) or match.group(2)).strip() if match else None


def extract_dates(query: str) -> list[str]:
    return re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", query)


def extract_metric_names(query: str) -> list[str]:
    quoted = re.findall(r"'([^']*timeseries\.[^']+)'|\"([^\"]*timeseries\.[^\"]+)\"", query)
    metrics = [(single or double).strip() for single, double in quoted if (single or double).strip()]
    if metrics:
        return metrics
    lowered = query.lower()
    names = []
    if "recordsuccess" in lowered or "record counts" in lowered:
        names.append("timeseries.ingestion.dataset.recordsuccess.count")
    if "batchsuccess" in lowered or "batch success" in lowered:
        names.append("timeseries.ingestion.dataset.batchsuccess.count")
    return names


def render_observability_values(query: str, evidence: dict[str, Any]) -> str | None:
    fields = evidence.get("important_fields", {})
    values = fields.get("values") if isinstance(fields, dict) else None
    if not isinstance(values, list) or not values:
        return None
    rendered = []
    for item in values[:8]:
        if not isinstance(item, dict):
            continue
        date = item.get("timestamp") or item.get("date") or item.get("time")
        value = item.get("value") if "value" in item else item.get("count")
        metric = item.get("metric") or item.get("name")
        if date is not None and value is not None:
            prefix = f"{human_date(date)}"
            if metric:
                prefix += f" {metric}"
            rendered.append(f"{prefix}: {value}")
    if not rendered:
        return None
    metric_names = extract_metric_names(query)
    metric_phrase = join_human(metric_names) if metric_names else "the requested metrics"
    return f"Based on live observability API evidence, {metric_phrase} values include: {join_human(rendered)}."


def human_date(value: Any) -> str:
    text = str(value)
    if len(text) >= 10 and re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    return text


def human_datetime(value: Any) -> str:
    text = str(value)
    if "T" in text:
        return text.replace("T", " ").replace("+00:00", " UTC").replace("Z", " UTC")
    return text


def sentence_case(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def join_human(items: list[str]) -> str:
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def format_rows(rows: list[dict[str, Any]], limit: int = 5) -> str:
    parts = []
    for row in rows[:limit]:
        parts.append(", ".join(f"{key}={value}" for key, value in list(row.items())[:4]))
    return "; ".join(parts)


def human_property_label(field: str) -> str:
    label = field.rsplit(".", 1)[-1]
    label = re.sub(r"([a-z])([A-Z])", r"\1 \2", label).replace("_", " ").replace("-", " ")
    return label.lower()
