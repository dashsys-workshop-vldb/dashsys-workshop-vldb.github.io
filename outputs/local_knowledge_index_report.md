# Local Knowledge Index Report

This report describes a Parquet-derived evidence-object index. It does not change packaged execution.

- Parquet files scanned: 18
- Tables indexed: 18
- Evidence objects: 1033
- Rejected objects: 0
- Data JSON used for runtime: False
- Local index returns final answers: False
- Packaged execution changed: False

## Evidence Types

- reusable_entity_lookup: 496
- reusable_schema_relation_lookup: 304
- reusable_value_grounding: 233

## Indexed Tables

- `br_campaign_segment`: rows=3 columns=4 domains=journey_campaign, segment_audience high_signal=[SEGMENTID, CAMPAIGNID, LABELSSEGMENT, LABELSCAMPAIGN]
- `dim_blueprint`: rows=74 columns=20 domains=batch, schema_dataset, observability, tags high_signal=[BLUEPRINTTYPE, UPDATEDCLIENTID, LABELSBLUEPRINT, UPDATEDTIME, CLASS, BLUEPRINTID, ISPROFILEENABLED, NAME]
- `dim_campaign`: rows=2 columns=21 domains=journey_campaign high_signal=[UPDATEDTIME, STARTDATE, LABELSCAMPAIGN, IMSORGID, LASTDEPLOYEDTIME, STATE, CAMPAIGNTYPE, STOPPEDTIME]
- `dim_collection`: rows=37 columns=16 domains=batch, schema_dataset high_signal=[ISIDENTITYENABLED, UPDATEDTIME, ISPROFILEENABLED, NAME, COLLECTIONID, CREATEDTIME, UPDATEDBY, CREATEDCLIENTID]
- `dim_connector`: rows=16 columns=14 domains=tags, destination_dataflow high_signal=[DATAFLOWNAME, UPDATEDTIME, CONNECTIONSPECNAME, STATE, SOURCEID, LABELSSOURCE, NAME, DATAFLOWID]
- `dim_property`: rows=27 columns=12 domains=general high_signal=[UPDATEDTIME, PARENTARTIFACTID, ALTDISPLAYTITLE, CREATEDTIME, PROPERTYID, LABELSPROPERTY, TYPE]
- `dim_segment`: rows=13 columns=19 domains=batch, schema_dataset, segment_audience, merge_policy high_signal=[SEGMENTID, UPDATEDTIME, SEGMENTBLUEPRINTCLASS, NAME, EVALUATIONCOMPLETEDTIME, LABELSSEGMENT, LIFECYCLESTATUS, ISBATCH]
- `dim_target`: rows=1 columns=11 domains=destination_dataflow high_signal=[DATAFLOWNAME, UPDATEDTIME, LABELSTARGET, STATE, TARGETID, CREATEDTIME, CONNECTIONSPECID, NAME]
- `hkg_br_base_segment_used_by_dependent_segment`: rows=0 columns=4 domains=segment_audience high_signal=[SEGMENTID, LABELSDEPENDENTSEGMENT, LABELSSEGMENT, DEPENDENTSEGMENTID]
- `hkg_br_blueprint_collection`: rows=27 columns=4 domains=schema_dataset high_signal=[COLLECTIONID, LABELSBLUEPRINT, BLUEPRINTID, LABELSCOLLECTION]
- `hkg_br_blueprint_property`: rows=27 columns=4 domains=schema_dataset high_signal=[LABELSBLUEPRINT, BLUEPRINTID, LABELSPROPERTY]
- `hkg_br_collection_property`: rows=27 columns=4 domains=schema_dataset high_signal=[COLLECTIONID, LABELSPROPERTY, LABELSCOLLECTION]
- `hkg_br_collection_segment`: rows=13 columns=4 domains=schema_dataset, segment_audience high_signal=[SEGMENTID, COLLECTIONID, LABELSSEGMENT, LABELSCOLLECTION]
- `hkg_br_property_property`: rows=0 columns=0 domains=general high_signal=[]
- `hkg_br_segment_property`: rows=19 columns=4 domains=segment_audience high_signal=[SEGMENTID, LABELSSEGMENT, LABELSPROPERTY]
- `hkg_br_segment_target`: rows=1 columns=4 domains=segment_audience, destination_dataflow high_signal=[SEGMENTID, LABELSSEGMENT, LABELSTARGET, TARGETID]
- `hkg_br_source_collection`: rows=15 columns=6 domains=schema_dataset, destination_dataflow high_signal=[DATAFLOWNAME, COLLECTIONID, DATAFLOWID, SOURCEID, LABELSSOURCE, LABELSCOLLECTION]
- `hkg_br_target_property`: rows=2 columns=4 domains=destination_dataflow high_signal=[LABELSTARGET, TARGETID, LABELSPROPERTY]

## Safety

- Evidence objects include provenance and explicitly mark `data_json_used=false`.
- The index returns evidence records only; final-answer composition remains a separate step.
- No final submission, official eval, scorer, or hidden-style test files are modified by this script.
