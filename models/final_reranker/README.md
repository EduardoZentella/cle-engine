# Final Reranker Drop-In Contract

This folder enables plug-and-play use of a pretrained final reranker model.

Backend behavior:

- if `manifest.json` and its `model_file` exist, backend uses the pretrained model,
- if artifacts are missing or invalid, backend automatically falls back to embedding similarity reranking.

## Required files for pretrained mode

1. `manifest.json`
2. model artifact referenced by `manifest.json:model_file` (for example `model.pkl`)

## Manifest format

```json
{
  "version": 1,
  "model_file": "model.pkl",
  "score_method": "predict_proba",
  "positive_class_index": 1,
  "threshold": 0.55,
  "feature_order": [
    "semantic_similarity",
    "fusion_score",
    "vector_score",
    "lexical_score",
    "llm_score",
    "source_vector",
    "source_lexical",
    "source_hybrid",
    "source_llm_refine"
  ]
}
```

## Score methods

- `predict_proba`: uses positive class probability at `positive_class_index`
- `decision_function`: converts outputs to probabilities with sigmoid
- `predict`: uses predicted values directly in [0, 1]
- `call`: calls model as callable with feature matrix
- `auto`: first supported method in this order: predict_proba, decision_function, predict, call

## Input feature schema

Each candidate row is converted to a feature vector using `feature_order`.
Available feature names:

- `semantic_similarity`
- `fusion_score`
- `vector_score`
- `lexical_score`
- `llm_score`
- `source_vector`
- `source_lexical`
- `source_hybrid`
- `source_llm_refine`

Unknown feature names are treated as `0.0`.

## Output expectations

The model should return one score per candidate row.
Scores are clamped to [0, 1].

## Runtime configuration

- `FINAL_RERANKER_MODEL_DIR` (default: `models/final_reranker`)
- `FINAL_RERANKER_MANIFEST_FILE` (default: `manifest.json`)
