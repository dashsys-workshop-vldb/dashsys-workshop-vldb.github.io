from __future__ import annotations

from dashagent.api_endpoint_repair import repair_api_call
from dashagent.endpoint_catalog import EndpointCatalog


def test_batch_files_alias_repairs_to_export_files(tiny_project):
    repaired = repair_api_call(
        "GET",
        "/data/core/ups/batch/abc/files",
        {},
        EndpointCatalog(tiny_project),
        query="Which files are available for download in batch abc?",
    )
    assert repaired["repaired"] is True
    assert repaired["url"] == "/data/foundation/export/batches/abc/files"


def test_failed_batch_files_alias_repairs_to_failed_endpoint(tiny_project):
    repaired = repair_api_call(
        "GET",
        "/data/core/ups/batch/abc/files",
        {},
        EndpointCatalog(tiny_project),
        query="Which failed files are in batch abc?",
    )
    assert repaired["repaired"] is True
    assert repaired["url"] == "/data/foundation/export/batches/abc/failed"


def test_unrelated_endpoint_does_not_repair(tiny_project):
    repaired = repair_api_call("GET", "/totally/unknown/path", {}, EndpointCatalog(tiny_project))
    assert repaired["repaired"] is False
