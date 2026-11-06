# Semantic skill candidate strategy

The suggestion candidate endpoint keeps its existing lexical ranker as the
default. To opt into semantic ranking, install the optional dependency and
download the model explicitly:

```powershell
python -m pip install -e ".[semantic]"
python scripts/download_semantic_model.py
```

Then request:

```text
GET /skills/suggestions/{suggestion_id}/candidates?strategy=semantic
```

Without the optional package or cached model, this request returns HTTP 503
with `error_code: semantic_engine_unavailable`. Inference uses FastEmbed with
`local_files_only=True`; it does not implicitly download a model or send
suggestion text to a hosted inference service. The explicit setup command needs
network access to fetch the model. The optional package is pinned to
`fastembed==0.9.1`. It uses ONNX Runtime rather than requiring PyTorch. The
selected `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model
supports multilingual sentence embeddings, including Turkish, has a 384-value
embedding and is listed at about 0.22 GB with an Apache-2.0 license by the
FastEmbed model catalog. Check the upstream model and package terms before
redistributing them.

The model is pretrained by Sentence Transformers; CareerTracker does not train
or fine-tune it. The returned value is cosine similarity normalized to the
existing 0..1 response range. It is a ranking score, not a probability or a
claim that two skills are equivalent. The original difflib/token-based
`strategy=lexical` remains the default and does not require this extra.

Semantic candidate vectors are cached in process memory for up to eight
catalog snapshots. The cache contains visible catalog text and embeddings and
is rebuilt when the catalog or a user's visible aliases change. It is not
persisted to the database. Visibility is applied before embedding: shared skills
and the requesting user's own skills/aliases are considered, while another
user's private skills and aliases remain excluded. The cache is process-local;
each server worker maintains its own copy.

## Synthetic evaluation

Run the small synthetic comparison with a locally cached model:

```powershell
python scripts/evaluate_semantic_skill_candidates.py
```

The script creates an in-memory SQLite database, loads the current skill seed,
and evaluates 16 manually authored Turkish/English descriptions against the
catalog. It prints lexical and semantic top-1, top-3 and MRR@10, along with the
first semantic call (including lazy model initialization) and warm-call timing.
It reads no user records and writes no evaluation data to the repository.

The observed probe result was:

| Strategy | Top-1 | Top-3 | MRR@10 |
|---|---:|---:|---:|
| Lexical | 1/16 | 1/16 | 0.0859 |
| Semantic | 2/16 | 8/16 | 0.3142 |

This is a tiny, hand-authored regression probe, not a representative accuracy
benchmark or evidence of real-world hiring performance. Timing depends on CPU,
model cache and catalog size; use the script's local timing output for the
current machine. On the reference Windows environment, the first call with a
180-skill catalog took 6.404 seconds including lazy model initialization, and
the mean of the 15 warm calls was 72.63 ms. The first call includes model
initialization, so compare it separately from warm calls.

## Failure behavior and limits

- Missing package/model: HTTP 503, `semantic_engine_unavailable`.
- Encoding or vector failure: HTTP 502, `semantic_engine_failed`.
- The endpoint still requires authentication and applies per-user skill
  visibility before ranking.
- There is no trained CareerTracker model and no real job-posting evaluation
  set in this slice.
