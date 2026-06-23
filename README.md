# RAG with Mistral AI Libraries

This demo uploads the Halfords 2025 annual report PDF into a Mistral AI Library, waits for Mistral to process the document, then exposes a small chat UI for retrieval-augmented questions.

## What the app does

1. Creates a Mistral Library with `POST /v1/libraries`.
2. Uploads a PDF with `POST /v1/libraries/{library_id}/documents`.
3. Polls `GET /v1/libraries/{library_id}/documents/{document_id}/status` until `process_status` is `done`.
4. Sends chat questions to `/v1/chat/completions` with a document library tool attached.

Mistral's current docs also show a simpler file retrieval path with `client.files.upload(..., purpose="retrieval")` and `documents=[{"type": "file", "id": file_id}]`. This project uses the beta Library API because the goal is to upload the annual report to a library.

## Setup

From `C:\Users\reach\anaconda3\RAG_Mistral`:

```powershell
cd backend
copy .env.example .env
```

Edit `backend\.env`:

```env
MISTRAL_API_KEY=your_mistral_api_key_here
HALFORDS_REPORT_URL=https://direct-link-to-halfords-2025-annual-report.pdf
```

If you do not have a direct PDF URL, leave `HALFORDS_REPORT_URL` blank and use the UI's local PDF upload instead.

## Run Backend

```powershell
cd C:\Users\reach\anaconda3\RAG_Mistral\backend
python -m pip install -r requirements.txt
python run.py
```

The API runs at `http://127.0.0.1:8000`.

## Run Frontend

In a second terminal:

```powershell
cd C:\Users\reach\anaconda3\RAG_Mistral\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Suggested Questions

- What were Halfords' key FY25 financial results?
- What are the main risks discussed in the annual report?
- Summarize the strategy and outlook.
- What changed in leadership or governance?

## Notes

- `backend\data\rag_state.json` stores the active `library_id`, `document_id`, and processing status.
- Mistral Library processing can take a few minutes for a large annual report.
- If chat returns a generic answer, check that `/api/status` reports `done`.
