# RAG Module

Module nay phu trach index va retrieve legal chunks bang Qdrant.

Input mac dinh:

```text
data/preprocessed/chunks/chunks.jsonl
```

Output index:

```text
Qdrant collection: legal_chunks
```

## Cau Truc

```text
src/pipeline/rag/
  index_chunks.py        # CLI index chunks vao Qdrant
  query_chunks.py        # CLI retrieve, giu tuong thich ten cu
  retrieve.py            # CLI retrieve ten moi
  ask.py                 # CLI RAG (retrieve + OpenRouter)
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
  legal_generator/
    config.py            # OpenRouter / LLM config
    generator.py         # LegalQAGenerator (ask + ask_stream)
    client.py            # OpenRouter client
    prompt.py            # system prompt + context format
    cli_ask.py
```

## Embedding

Mac dinh giu dung model trong code cu:

- Dense: `bkai-foundation-models/vietnamese-bi-encoder`
- Sparse/BM25: `Qdrant/bm25`
- Dense vector name: `dense`
- Sparse vector name: `sparse`

Text de embed:

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

Payload index chi tao 3 field phuc vu filter:

- `document_number`
- `effective_from_int`
- `effective_to_int`

Payload van luu cac field citation can thiet nhu `chunk_id`, `source_unit_ids`,
`document_title`, `document_type`, `path_text`, `content`, `effective_from`,
`effective_to`, `source_file`, `source_url`.

## Index

```powershell
& 'D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe' src\pipeline\rag\index_chunks.py --recreate
```

Test nhanh voi local Qdrant:

```powershell
& 'D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe' src\pipeline\rag\index_chunks.py --local-qdrant --recreate --limit 200
```

## Retrieve

Mode ho tro:

- `dense`
- `sparse`
- `hybrid`

Neu khong truyen filter, retrieval chay tren toan bo collection. Neu truyen
`--document-number` hoac `--as-of`, filter duoc day xuong Qdrant.

```powershell
& 'D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe' src\pipeline\rag\retrieve.py "dieu kien cap giay phep lai xe" --mode hybrid --top 5
```

Filter theo van ban:

```powershell
& 'D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe' src\pipeline\rag\retrieve.py "hieu luc thi hanh" --document-number "161/2024/ND-CP" --mode dense
```

Filter theo hieu luc:

```powershell
& 'D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe' src\pipeline\rag\retrieve.py "xu phat nguoi dieu khien xe" --as-of 2025-01-01 --mode sparse
```

## Ask (RAG)

Can hoi tra loi bang OpenRouter sau khi retrieve:

```powershell
$env:PYTHONPATH="src\pipeline\rag"
& 'D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe' src\pipeline\rag\ask.py "Hoi dong nhan dan Ha Noi co tham quyen gi ve dau tu cong"
```

Can `.env` o root project:

```env
QDRANT_URL=...
QDRANT_API_KEY=...
OPENROUTER_API_KEY=...
```

## Web (ai-service + backend + frontend)

```powershell
cd ai-service; pip install -r requirements.txt; python main.py
cd backend; pip install -r requirements.txt; python main.py
cd frontend; python serve.py
```

- AI service: `http://127.0.0.1:8001` (RAG + SSE)
- Backend BFF: `http://127.0.0.1:8000` (proxy)
- Frontend: `http://127.0.0.1:5173`
