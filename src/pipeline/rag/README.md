# RAG Module

`src/pipeline/rag` chi phu trach embedding, index va retrieve legal chunks.
Module nay khong sinh cau tra loi va khong goi LLM.

## Input

```text
data/preprocessed/chunks/chunks.jsonl
```

## Output

```text
Qdrant collection: legal_chunks
```

## Cau Truc

```text
src/pipeline/rag/
  index_chunks.py        # CLI index chunks vao Qdrant
  retrieve.py            # CLI retrieve chunks tu Qdrant
  legal_rag/
    config.py            # config dataclass
    env.py               # doc .env
    embedder.py          # dense + sparse embedding
    filters.py           # payload va filter
    store.py             # Qdrant collection/index setup
    indexer.py           # batch embed + upsert
    retriever.py         # dense/sparse/hybrid retrieval
    cli_index.py
    cli_retrieve.py
```

Generation/answer nam o:

```text
src/pipeline/agents/
src/pipeline/core/
src/pipeline/prompts/
```

## Embedding

- Dense: `bkai-foundation-models/vietnamese-bi-encoder`
- Sparse/BM25: `Qdrant/bm25`
- Dense vector name: `dense`
- Sparse vector name: `sparse`

Text dung de embed:

```text
document_number
path_text
content
```

## Qdrant

Qdrant Cloud la mac dinh neu `.env` co:

```env
QDRANT_URL=https://<cluster>.cloud.qdrant.io
QDRANT_API_KEY=<api-key>
```

Payload index tao cac field phuc vu filter:

- `document_number`
- `effective_from_int`
- `effective_to_int`

Payload van luu cac field citation can thiet nhu `chunk_id`, `source_unit_ids`,
`document_title`, `document_type`, `path_text`, `content`, `effective_from`,
`effective_to`, `source_file`, `source_url`.

## Index

```powershell
python src\pipeline\rag\index_chunks.py --recreate
```

Test nhanh voi local Qdrant:

```powershell
python src\pipeline\rag\index_chunks.py --local-qdrant --recreate --limit 200
```

## Retrieve

Mode ho tro:

- `dense`
- `sparse`
- `hybrid`

Neu khong truyen filter, retrieval chay tren toan bo collection. Neu truyen
`--document-number` hoac `--as-of`, filter duoc day xuong Qdrant.

```powershell
python src\pipeline\rag\retrieve.py "dieu kien cap giay phep lai xe" --mode hybrid --top 5
```

Filter theo van ban:

```powershell
python src\pipeline\rag\retrieve.py "hieu luc thi hanh" --document-number "161/2024/ND-CP" --mode dense
```

Filter theo hieu luc:

```powershell
python src\pipeline\rag\retrieve.py "xu phat nguoi dieu khien xe" --as-of 2025-01-01 --mode sparse
```
