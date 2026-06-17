# AI Agent

Repo nay chia engine AI thanh 3 phan ro rang:

- `src/pipeline/data_preprocessing`: parse, extract effectivity, build chunks.
- `src/pipeline/rag`: embedding, Qdrant index va retrieve chunks.
- `src/pipeline/agents`, `src/pipeline/core`, `src/pipeline/prompts`: sinh cau tra loi tu question va retrieved contexts.

`rag` khong chua code goi LLM. Neu can hoi-dap end-to-end, service/orchestrator se goi `rag` truoc, sau do goi `AnswerAgent`.

## Moi Truong

Dung Python 3.10.

Neu chay bang package import, them root project hoac `src` vao `PYTHONPATH` tuy cach chay:

```powershell
$env:PYTHONPATH="src"
```

## Data Preprocessing

Parse dataset package:

```powershell
python src\pipeline\data_preprocessing\parser\parse_package.py `
  --input data\dataset `
  --output data\preprocessed\parsed `
  --no-convert-doc
```

Extract effectivity:

```powershell
python src\pipeline\data_preprocessing\effectivity\extract_effectivity.py `
  --input data\preprocessed\parsed `
  --output data\preprocessed\effectivity
```

Build chunks:

```powershell
python src\pipeline\data_preprocessing\chunker\chunk_dataset.py `
  --input data\preprocessed\parsed `
  --effectivity data\preprocessed\effectivity `
  --output data\preprocessed\chunks
```

## RAG

Index chunks vao Qdrant:

```powershell
python src\pipeline\rag\index_chunks.py --recreate
```

Retrieve chunks:

```powershell
python src\pipeline\rag\retrieve.py "dieu kien cap giay phep lai xe" --mode hybrid --top 5
```

Chi tiet: `src/pipeline/rag/README.md`.

## Answer Agent

`AnswerAgent` nhan question va contexts da retrieve, sau do goi LLM qua `src/pipeline/core/llm.py`.

```powershell
python src\pipeline\agents\answer.py "Cau hoi phap ly" --contexts retrieved_contexts.jsonl
```

Can `.env` o root project neu goi OpenRouter:

```env
OPENROUTER_API_KEY=<api-key>
QDRANT_URL=https://<cluster>.cloud.qdrant.io
QDRANT_API_KEY=<api-key>
```

## Web Services

Web layer hien co 3 service:

```text
Frontend :5173 -> Backend :8000 -> AI Service :8001
```

AI service dung pipeline dung: `ChunkRetriever` de retrieve, sau do `AnswerAgent` de sinh cau tra loi.

```powershell
cd ai-service
pip install -r requirements.txt
python main.py
```

```powershell
cd backend
pip install -r requirements.txt
python main.py
```

```powershell
cd frontend
python serve.py
```
