from pathlib import Path
from typing import Any
from typing import Literal

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import get_settings
from .mistral_client import MistralRagClient
from .state import data_root, read_state, write_state


app = FastAPI(title="RAG with Mistral AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestUrlRequest(BaseModel):
    url: str | None = None
    library_name: str | None = None
    wait: bool = True


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []
    library_id: str | None = None


def _download_pdf(url: str) -> Path:
    if not url:
        raise HTTPException(
            status_code=400,
            detail="Provide a report URL or set HALFORDS_REPORT_URL in backend/.env.",
        )
    target = data_root() / "halfords_annual_report_2025.pdf"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"The URL did not look like a PDF. Content-Type: {content_type}")
    target.write_bytes(response.content)
    return target


def _ensure_library(client: MistralRagClient, library_name: str | None) -> str:
    state = read_state()
    if state.get("library_id"):
        return state["library_id"]
    settings = get_settings()
    library = client.create_library(
        library_name or settings.default_library_name,
        "RAG demo library for the Halfords 2025 annual report.",
    )
    library_id = library["id"]
    write_state({"library_id": library_id, "library": library})
    return library_id


def _upload_and_optionally_wait(file_path: Path, library_name: str | None, wait: bool) -> dict:
    client = MistralRagClient()
    library_id = _ensure_library(client, library_name)
    document = client.upload_document(library_id, file_path)
    document_id = document["id"]
    result = {
        "library_id": library_id,
        "document_id": document_id,
        "document": document,
        "status": document.get("process_status"),
    }
    write_state(result)
    if wait:
        status = client.wait_until_processed(library_id, document_id)
        result["status"] = status.get("process_status")
        result["status_detail"] = status
        write_state({"status": result["status"], "status_detail": status})
    return result


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text") or item.get("content") or item.get("value")
                if isinstance(value, str):
                    parts.append(value)
        return "\n".join(part.strip() for part in parts if part and part.strip())
    return ""


def _extract_answer(response: dict[str, Any]) -> str:
    outputs = response.get("outputs") or []
    for output in reversed(outputs):
        if isinstance(output, dict) and output.get("type") == "message.output":
            text = _text_from_content(output.get("content"))
            if text:
                return text

    choices = response.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        text = _text_from_content(message.get("content"))
        if text:
            return text
        messages = choice.get("messages") or []
        for nested in reversed(messages):
            text = _text_from_content(nested.get("content"))
            if text:
                return text

    return ""


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "state": read_state()}


@app.post("/api/ingest/url")
def ingest_from_url(payload: IngestUrlRequest) -> dict:
    settings = get_settings()
    file_path = _download_pdf(payload.url or settings.halfords_report_url)
    return _upload_and_optionally_wait(file_path, payload.library_name, payload.wait)


@app.post("/api/ingest/upload")
async def ingest_upload(file: UploadFile = File(...), wait: bool = True, library_name: str | None = None) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")
    suffix = Path(file.filename).suffix or ".pdf"
    target = data_root() / f"uploaded_report{suffix}"
    target.write_bytes(await file.read())
    return _upload_and_optionally_wait(target, library_name, wait)


@app.get("/api/status")
def status(library_id: str | None = None, document_id: str | None = None) -> dict:
    state = read_state()
    library = library_id or state.get("library_id")
    document = document_id or state.get("document_id")
    if not library or not document:
        return {"status": "not_uploaded", "state": state}
    latest = MistralRagClient().document_status(library, document)
    write_state({"status": latest.get("process_status"), "status_detail": latest})
    return latest


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    state = read_state()
    library_id = payload.library_id or state.get("library_id")
    if not library_id:
        raise HTTPException(status_code=400, detail="No library has been created yet. Upload or ingest the PDF first.")
    messages = [message.model_dump() for message in payload.history]
    messages.append({"role": "user", "content": payload.question})
    client = MistralRagClient()
    response = client.chat(library_id, messages)
    answer = _extract_answer(response)
    if not answer:
        fallback_response = client.chat_completions_fallback(library_id, messages)
        answer = _extract_answer(fallback_response)
        response = {"conversation_response": response, "chat_completion_response": fallback_response}
    if not answer:
        answer = (
            "Mistral accepted the request but did not return a final text answer. "
            "I saved the raw response at backend/data/last_mistral_response.json so we can inspect the exact API output."
        )
    return {"answer": answer, "raw": response}
