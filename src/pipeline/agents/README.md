# Agents Module

`src/pipeline/agents` phu trach sinh cau tra loi tu question va retrieved contexts.
Module nay khong parse du lieu, khong embedding, khong index, va khong retrieve Qdrant.

Pipeline dung:

```text
data_preprocessing -> rag retrieve -> agents answer
```

## Input

`AnswerAgent` nhan:

- `question`: cau hoi cua nguoi dung.
- `contexts`: danh sach chunk da retrieve tu `src/pipeline/rag`.

Context row nen co cac field citation neu co:

```json
{
  "score": 0.8123,
  "mode": "hybrid",
  "chunk_id": "...",
  "source_unit_ids": ["..."],
  "document_number": "...",
  "document_title": "...",
  "document_type": "...",
  "path_text": "...",
  "effective_from": "YYYY-MM-DD",
  "effective_to": null,
  "source_file": "...",
  "source_url": "...",
  "content": "..."
}
```

## Output

```python
AnswerResult(
    answer="...",
    contexts=[...],
    model="..."
)
```

## Cau Truc

```text
src/pipeline/agents/
  answer.py             # CLI demo answer tu question + optional contexts
  answer_agent.py       # AnswerAgent
  README.md
  requirements.txt

src/pipeline/core/
  llm.py                # OpenRouterLLM stdlib client

src/pipeline/prompts/
  answer.py             # system prompt + context formatting
```

## Requirements

Agents hien khong can third-party Python package rieng. LLM client dung Python
stdlib (`urllib`) de goi OpenRouter.

```powershell
pip install -r src\pipeline\agents\requirements.txt
```

Can `.env` o root project khi goi LLM:

```env
OPENROUTER_API_KEY=<api-key>
```

Tuy chon:

```env
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_APP_URL=<app-url>
OPENROUTER_APP_NAME=<app-name>
```

## CLI

Hoi khong co retrieved contexts:

```powershell
python src\pipeline\agents\answer.py "Cau hoi phap ly"
```

Hoi voi contexts tu file JSONL:

```powershell
python src\pipeline\agents\answer.py "Cau hoi phap ly" --contexts retrieved_contexts.jsonl
```

Filter contexts theo cung field ma `rag.retrieve` tra ve:

```powershell
python src\pipeline\agents\answer.py "Cau hoi phap ly" `
  --contexts retrieved_contexts.jsonl `
  --document-number "161/2024/ND-CP" `
  --as-of 2025-01-01 `
  --top 5 `
  --min-score 0.5 `
  --mode hybrid
```

Override model/temperature/token limit:

```powershell
python src\pipeline\agents\answer.py "Cau hoi phap ly" `
  --contexts retrieved_contexts.jsonl `
  --model openai/gpt-4o-mini `
  --temperature 0.0 `
  --max-tokens 1024
```

## Dung Nhu Package

```python
from src.pipeline.agents import AnswerAgent

agent = AnswerAgent()
result = agent.answer(
    "Cau hoi phap ly",
    contexts=retrieved_chunks,
    document_number="161/2024/ND-CP",
    as_of_date="2025-01-01",
    top_k=5,
    min_score=0.5,
    mode="hybrid",
    model="openai/gpt-4o-mini",
    temperature=0.0,
    max_tokens=1024,
)
print(result.answer)
```

## Context Filters

Filter cua `agents` chi loc tren danh sach contexts da duoc truyen vao. No khong
goi Qdrant va khong thay the `rag.retrieve`.

- `document_number`: so khop chinh xac voi field `document_number`.
- `as_of_date` / CLI `--as-of`: giu contexts co `effective_from <= as_of` va `effective_to > as_of`; null/empty duoc xem la khong gioi han.
- `top_k` / CLI `--top`: lay N contexts dau tien sau khi filter, giu nguyen thu tu score cua retrieve.
- `min_score`: giu contexts co `score >= min_score`.
- `mode`: so khop voi field `mode` (`dense`, `sparse`, `hybrid`).

## Ranh Gioi Trach Nhiem

- `agents`: prompt orchestration va answer generation.
- `core`: LLM client dung chung.
- `prompts`: prompt templates va context formatting.
- `rag`: chi retrieve contexts, khong goi LLM.
- `data_preprocessing`: chi tao parsed/effectivity/chunks.
