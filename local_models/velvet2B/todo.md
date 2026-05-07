PLAN FOR INFERENCE SETUP CREATION.

- expand form single source to a recipe! create a loader (read multiple folders in jsonl/jsonl.gz/parquet extensions, load files in parquet or jsonl.gz)

- reinforce with a BASE inference schema as metadata (3 schemas: positive, negative, candidate) AND FINAL inference (3 schemas: positiveS, negativeS, candidateS) schema in a jsonfile.

- enforce with system prompt as metadata, not only multiple temperatures! (k-variants logging)

- use parametric ENUM to decide the SCHEMA! candidates,positive, negative. NOTA: singular value, not an array, we merge variants later by same hash_id!

- FINAL inference schema  aggregates unit base results into an array, merged_by same hash_id!

- after aggregation, results are converted from N jsonl files to N parquet files for efficiency! 


BASE INFERENCE SCHEMAS: (3 variants splitted by '|')
```json
{
   "_id_hash": {
        "type": "string",
        "pattern": "^[a-fA-F0-9]{64}$"
    },
    "_distribution_name":{
        "type":"string"
    },
    "positive | negative | candidate": {
        "type": "object",
        "required": [
            "content",
            "score",
            "inference_params"
        ],
        "properties": {
            "score": {
                "type": "number",
                "maximum": 1,
                "minimum": 0
            },
            "think": {
                "type": [
                    "string",
                    "null"
                ]
            },
            "content": {
                "type": "string",
                "minLength": 1
            },
            "context": {
                "type": [
                    "string",
                    "null"
                ]
            },
            "inference_params": {
                "type": [
                    "object",
                    "null"
                ],
                "properties": {
                    "system_prompt_id":{
                        "type": [
                            "string",
                            "null"
                        ]
                    },
                    "top_k": {
                        "type": "number"
                    },
                    "top_p": {
                        "type": "number"
                    },
                    "model_id": {
                        "type": "string"
                    },
                    "temperature": {
                        "type": "number"
                    }
                },
                "additionalProperties": false
            }
        },
        "additionalProperties": false
    }
}
```

FINAL INFERENCE SCHEMAS (aggregated by "_id_hash"): (3 variants splitted by '|')

```json
{
   "_id_hash": {
        "type": "string",
        "pattern": "^[a-fA-F0-9]{64}$"
    },
    "_distribution_name":{
        "type":"string"
    },
    "positives | negatives | candidates": {
        "type":"array",
        "items":{
            "type": "object",
            "required": [
                "content",
                "score",
                "inference_params"
            ],
            "properties": {
                "score": {
                    "type": "number",
                    "maximum": 1,
                    "minimum": 0
                },
                "think": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
                "content": {
                    "type": "string",
                    "minLength": 1
                },
                "context": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
                "inference_params": {
                    "type": [
                        "object",
                        "null"
                    ],
                    "properties": {
                        "system_prompt_id":{
                            "type": [
                                "string",
                                "null"
                            ]
                        },
                        "top_k": {
                            "type": "number"
                        },
                        "top_p": {
                            "type": "number"
                        },
                        "model_id": {
                            "type": "string"
                        },
                        "temperature": {
                            "type": "number"
                        }
                    },
                    "additionalProperties": false
                }
            },
            "additionalProperties": false
        }
    }
}
```

RECIPE EXAMPLE (we are interested only in entries):
we have to extract only:
- 'dist_name' to inject it into "_distribution_name" 
- replica as a integer multiplier (in a way that 2 identical samples may have different system prompts)
- uri that identify location where read the files 
- "system_prompt" to impute it during inference (TO DEFINE HOW)
- "system_prompt_id" attach it to "inference_params" in a way to trace it

```yml
id: 55916616-d54f-4580-be79-b8f87b25392e
name: r2
description: r2
scope: continual_ft
tasks:
- information_extraction
- instruction_following
- mathematical_problem_solving
tags:
- a
- b
- c
derived_from: b0930b47-4c40-4015-9ece-2653bc80160d
entries:
  /Users/T.Finizzi/repo/SFT-data-Forge/nfs/mapped-data/velvet_v1/allenai/ai2_arc/ARC-Challenge/en:
    dist_id: a9a55ac3-e220-480d-a06e-cc4005960414
    dist_name: mapped__ARC-Challenge__en
    dist_uri: /Users/T.Finizzi/repo/SFT-data-Forge/nfs/mapped-data/velvet_v1/allenai/ai2_arc/ARC-Challenge/en
    chat_type: context_chat
    system_prompt: &id001
    - p1_content
    system_prompt_name: &id002
    - p1
    replica: 1
    samples: 2590
    tokens: 179178
    words: 129464
    validation_error: null
  /Users/T.Finizzi/repo/SFT-data-Forge/nfs/mapped-data/velvet_v1/allenai/ai2_arc/ARC-Challenge/downsampled__0.7__en:
    dist_id: 7efdecb2-6176-468b-be5e-06d55d283cc3
    dist_name: Downsampled__0.70__mapped__ARC-Challenge__en
    dist_uri: /Users/T.Finizzi/repo/SFT-data-Forge/nfs/mapped-data/velvet_v1/allenai/ai2_arc/ARC-Challenge/downsampled__0.7__en
    chat_type: context_chat
    replica: 1
    system_prompt: *id001
    system_prompt_name: *id002
    samples: 1812
    tokens: 125424
    words: 90624
```