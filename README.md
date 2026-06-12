# AI Agent

Pipeline hiện tại chỉ giữ phần tiền xử lý cần thiết cho văn bản pháp luật:

- `src/agent/data_preprocessing/parser`: parse file `.doc`/`.docx` thành cây JSON và `units.jsonl` tối thiểu.
- `src/agent/data_preprocessing/effectivity`: đọc thông tin hiệu lực chung/rieng từ `units.jsonl`.

Thư mục dữ liệu mặc định:

- Input: `data/dataset`
- Output parser: `data/preprocessed/parsed`
- Output effectivity: `data/preprocessed/effectivity`

## Môi Trường

Dùng Python 3.10. Trên máy hiện tại:

```powershell
D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe --version
```

Nếu chạy bằng package import, thêm `src` vào `PYTHONPATH`:

```powershell
$env:PYTHONPATH="src"
```

## Chạy Parser

Parse toàn bộ dataset package:

```powershell
& "D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe" `
  src\agent\data_preprocessing\parser\parse_package.py `
  --input data\dataset `
  --output data\preprocessed\parsed `
  --no-convert-doc
```

Mỗi package output gồm:

- `package_inventory.json`
- `main/tree.json`
- `main/units.jsonl`
- `attachments/<attachment>/tree.json`
- `attachments/<attachment>/attachment.json`

`units.jsonl` chỉ giữ field tối thiểu cho effectivity:

```json
{
  "id": "...",
  "document_id": "...",
  "document_number": "...",
  "issue_date": "...",
  "type": "...",
  "path_text": "...",
  "content": "..."
}
```

## Chạy Effectivity

Sau khi parser tạo `main/units.jsonl`, chạy:

```powershell
& "D:\Users\ADMIN\miniconda3\envs\py3.10\python.exe" `
  src\agent\data_preprocessing\effectivity\extract_effectivity.py `
  --input data\preprocessed\parsed `
  --output data\preprocessed\effectivity
```

Output effectivity:

- `data/preprocessed/effectivity/<package>/effectivity.json`
- `data/preprocessed/effectivity/effectivity_general.json`
- `data/preprocessed/effectivity/effectivity_units.json`

`effectivity_general.json` chứa hiệu lực chung của văn bản:

```json
{
  "document_id": "...",
  "document_number": "...",
  "effective_from": "YYYY-MM-DD",
  "effective_to": null,
  "effective_to_source_document_number": null,
  "in_corpus": true
}
```

`effectivity_units.json` chứa hiệu lực riêng cho điều/khoản/điểm khi văn bản có quy định riêng.

## Chạy Web (3 service)

Giao diện chat tra cứu pháp luật gồm 3 service chạy song song:

```text
Frontend :5173  →  Backend :8000 (BFF proxy)  →  AI Service :8001 (RAG + SSE)
```

| Service | Thư mục | Port | Vai trò |
|---------|---------|------|---------|
| AI service | `ai-service/` | 8001 | Retrieve chunks (Qdrant) + sinh câu trả lời (OpenRouter), SSE streaming |
| Backend | `backend/` | 8000 | Proxy HTTP/SSE tới AI service |
| Frontend | `frontend/` | 5173 | Giao diện chat, gọi API qua backend |

### Biến môi trường

Tạo file `.env` ở root project:

```env
QDRANT_URL=https://<cluster>.cloud.qdrant.io
QDRANT_API_KEY=<api-key>
OPENROUTER_API_KEY=<api-key>
```

Tùy chọn (backend dùng khi proxy):

```env
AI_SERVICE_URL=http://127.0.0.1:8001
```

### Khởi động (3 terminal)

**Terminal 1 — AI service** (lần đầu load embedder có thể mất ~30–60 giây):

```powershell
cd ai-service
pip install -r requirements.txt
python main.py
```

**Terminal 2 — Backend:**

```powershell
cd backend
pip install -r requirements.txt
python main.py
```

**Terminal 3 — Frontend:**

```powershell
cd frontend
python serve.py
```

Mở trình duyệt: http://127.0.0.1:5173

Frontend mặc định gọi backend tại `http://127.0.0.1:8000` (cấu hình trong `frontend/config.js`). Kiểm tra health:

```powershell
curl http://127.0.0.1:8001/api/health
curl http://127.0.0.1:8000/api/health
```

Chi tiết index/retrieve/CLI RAG: xem `src/pipeline/rag/README.md`.

## Lưu Ý

Parser không ghi thông tin cho embedding, reference resolving, amendment graph hay flat table index. Effectivity không ghi event log/CSV trung gian; chỉ ghi thông tin hiệu lực chung và riêng.
