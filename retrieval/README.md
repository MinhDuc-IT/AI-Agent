# Retrieval Pipeline

## Bước 1 — Tạo chunk từ passage (atomic only)

Input:

```text
data/preprocessed/passages/<PACKAGE_ID>/passages.jsonl
```

Output:

```text
data/preprocessed/chunks/<PACKAGE_ID>/chunks.jsonl
data/preprocessed/chunks/all_chunks.jsonl
data/preprocessed/chunks/chunk_summary.json
```

Mỗi chunk gồm 5 trường nội dung chính:

- `document_title`
- `path_text`
- `content`
- `effective_from`
- `effective_to`

Kèm các trường định danh phục vụ index/query sau này:

- `chunk_id` (= `passage_id`)
- `package_id`
- `document_number`

Chỉ lấy `passage_kind == "atomic"`, bỏ `container`.

### Chạy (Windows CMD)

```cmd
cd retrieval
python build_chunks.py -i "../data/preprocessed/passages" -o "../data/preprocessed/chunks"
```

Một package:

```cmd
python build_chunks.py -i "../data/preprocessed/passages/01_2024_NDCP" -o "../data/preprocessed/chunks"
```

## Bước 2 — Embed + index Qdrant hybrid

Cài dependency:

```cmd
cd retrieval
pip install -r requirements.txt
```

### Qdrant Cloud (mặc định)

Đặt trong `.env` ở root project:

```env
QDRANT_URL=https://<cluster>.cloud.qdrant.io
QDRANT_API_KEY=<api-key>
```

Index/query sẽ **tự đọc `.env`** và kết nối cloud (không cần truyền URL/key trên CLI).

```cmd
python index_chunks.py --recreate
python index_chunks.py --recreate --device cuda --batch-size 8
python query_chunks.py "hiệu lực thi hành" --as-of 2024-06-01 --top 5
```

Dùng Qdrant local thay vì cloud:

```cmd
python index_chunks.py --local-qdrant --recreate
python query_chunks.py "..." --local-qdrant
```

Corpus ~99k chunk trên CPU có thể mất vài giờ.

Test nhanh 200 chunk:

```cmd
python index_chunks.py -i "../data/preprocessed/chunks" --qdrant-path "../data/preprocessed/qdrant" --recreate --limit 200
```

Query hybrid (BM25 + dense bkai), top 5:

```cmd
python query_chunks.py "điều kiện cấp giấy phép lái xe" --as-of 2024-06-01 --top 5
python query_chunks.py "Điều 5 thu phí" --document-number "119/2021/ND-CP" --as-of 2024-06-01
```

### Chi tiết bước 2

- **Dense**: `bkai-foundation-models/vietnamese-bi-encoder` (768 dim, `max_seq_length=256`)
- **Sparse/BM25**: `Qdrant/bm25` qua `fastembed`
- **Fusion**: Reciprocal Rank Fusion (RRF)
- **Text embed**: `document_number` + `path_text` + `content`
- **Metadata filter**:
  - `effective_from <= as_of` hoặc null
  - `effective_to > as_of` hoặc null
  - `document_number` exact match (tuỳ chọn)

Output Qdrant local:

```text
data/preprocessed/qdrant/
```

## Pipeline tổng thể (đã chốt)

```text
passages.jsonl
    ↓  build_chunks.py
chunks.jsonl
    ↓  index_chunks.py
Qdrant (dense + sparse)
    ↓  query_chunks.py
Query
  ├─ Metadata filter: effective_from, effective_to, document_number
  ├─ BM25/keyword
  └─ Dense semantic
         ↓
  top 5
```
