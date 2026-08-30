# Pure LLM Dynamic Example Retrieval

Diagnostic-only report. Examples are generic SQL skeletons, not gold answers.

## How many journeys are published?

- Retrieved tables: `['dim_campaign', 'dim_property', 'dim_connector', 'dim_blueprint']`
- Pattern: count entities, optionally filtered by status or name | Skeleton: `SELECT COUNT(DISTINCT "IMSORGID") AS count FROM "dim_campaign" WHERE "STATE" = ?`
- Pattern: lookup published or deployed timestamp by named entity | Skeleton: `SELECT "SANDBOXNAME", "LASTDEPLOYEDTIME" FROM "dim_campaign" WHERE "SANDBOXNAME" = ? LIMIT ?`
- Pattern: list entity IDs and names | Skeleton: `SELECT "IMSORGID", "SANDBOXNAME" FROM "dim_campaign" LIMIT ?`
- Pattern: lookup created timestamp by named entity | Skeleton: `SELECT "SANDBOXNAME", "CREATEDTIME" FROM "dim_campaign" WHERE "SANDBOXNAME" = ? LIMIT ?`

## When was the journey 'Welcome Journey' published?

- Retrieved tables: `['dim_campaign', 'dim_connector', 'dim_blueprint', 'dim_collection']`
- Pattern: lookup entity status by quoted or named entity | Skeleton: `SELECT "SANDBOXNAME", "STATE" FROM "dim_campaign" WHERE "SANDBOXNAME" = ? LIMIT ?`
- Pattern: lookup published or deployed timestamp by named entity | Skeleton: `SELECT "SANDBOXNAME", "LASTDEPLOYEDTIME" FROM "dim_campaign" WHERE "SANDBOXNAME" = ? LIMIT ?`
- Pattern: count entities, optionally filtered by status or name | Skeleton: `SELECT COUNT(DISTINCT "IMSORGID") AS count FROM "dim_campaign" WHERE "STATE" = ?`
- Pattern: list entity IDs and names | Skeleton: `SELECT "IMSORGID", "SANDBOXNAME" FROM "dim_campaign" LIMIT ?`

## List dataset names and IDs.

- Retrieved tables: `['dim_collection', 'dim_campaign', 'dim_connector', 'dim_blueprint']`
- Pattern: list entity IDs and names | Skeleton: `SELECT "COLLECTIONID", "NAME" FROM "dim_collection" LIMIT ?`
- Pattern: count entities, optionally filtered by status or name | Skeleton: `SELECT COUNT(DISTINCT "COLLECTIONID") AS count FROM "dim_collection" WHERE "STATE" = ?`
- Pattern: lookup created timestamp by named entity | Skeleton: `SELECT "NAME", "CREATEDTIME" FROM "dim_collection" WHERE "NAME" = ? LIMIT ?`
- Pattern: lookup entity status by quoted or named entity | Skeleton: `SELECT "NAME", "STATE" FROM "dim_collection" WHERE "NAME" = ? LIMIT ?`

## What is the status of active destinations?

- Retrieved tables: `['dim_target', 'dim_segment', 'dim_campaign', 'dim_collection']`
- Pattern: lookup entity status by quoted or named entity | Skeleton: `SELECT "DATAFLOWNAME", "STATE" FROM "dim_target" WHERE "DATAFLOWNAME" = ? LIMIT ?`
- Pattern: count entities, optionally filtered by status or name | Skeleton: `SELECT COUNT(DISTINCT "TARGETID") AS count FROM "dim_target" WHERE "STATE" = ?`
- Pattern: list entity IDs and names | Skeleton: `SELECT "TARGETID", "DATAFLOWNAME" FROM "dim_target" LIMIT ?`
- Pattern: lookup published or deployed timestamp by named entity | Skeleton: `SELECT "DATAFLOWNAME", "LASTDEPLOYEDTIME" FROM "dim_target" WHERE "DATAFLOWNAME" = ? LIMIT ?`
