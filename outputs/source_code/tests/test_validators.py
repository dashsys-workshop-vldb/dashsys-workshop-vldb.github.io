from __future__ import annotations

from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.schema_index import SchemaIndex
from dashagent.validators import APIValidator, SQLValidator


def test_sql_validator_catches_fake_table_and_column(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    validator = SQLValidator(schema)

    fake_table = validator.validate("SELECT * FROM made_up_table")
    assert fake_table.ok is False
    assert any("Unknown table" in error for error in fake_table.errors)

    fake_column = validator.validate('SELECT fake_col FROM "dim_campaign"')
    assert fake_column.ok is False
    assert any("Unknown column" in error for error in fake_column.errors)


def test_api_validator_rejects_unknown_endpoint(tiny_project):
    catalog = EndpointCatalog(tiny_project)
    validator = APIValidator(catalog)
    result = validator.validate("GET", "/not/a/real/endpoint", {}, {})
    assert result.ok is False
    assert "Unknown" in result.errors[0]


def test_endpoint_catalog_loads(tiny_project):
    catalog = EndpointCatalog(tiny_project)
    assert catalog.match("GET", "/ajo/journey") is not None
    assert catalog.match("GET", "/data/foundation/schemaregistry/tenant/schemas/abc123456789") is not None
