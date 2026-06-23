import time
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException

from .config import get_settings
from .state import data_root


DONE_STATUSES = {"done", "noop", "self_managed"}
FAILED_STATUSES = {"error", "missing_content"}


class MistralRagClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.mistral_api_key:
            raise HTTPException(
                status_code=400,
                detail="MISTRAL_API_KEY is not configured. Add it to backend/.env or your shell environment.",
            )
        self.base_url = settings.mistral_base_url.rstrip("/")
        self.model = settings.mistral_model
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {settings.mistral_api_key}"})

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(method, f"{self.base_url}{path}", timeout=120, **kwargs)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return response.text

    def create_library(self, name: str, description: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        return self._request("POST", "/libraries", json=payload)

    def upload_document(self, library_id: str, file_path: Path) -> dict[str, Any]:
        with file_path.open("rb") as handle:
            files = {"file": (file_path.name, handle, "application/pdf")}
            return self._request("POST", f"/libraries/{library_id}/documents", files=files)

    def document_status(self, library_id: str, document_id: str) -> dict[str, Any]:
        return self._request("GET", f"/libraries/{library_id}/documents/{document_id}/status")

    def wait_until_processed(
        self,
        library_id: str,
        document_id: str,
        timeout_seconds: int = 900,
        poll_seconds: int = 5,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        latest: dict[str, Any] = {}
        while time.monotonic() < deadline:
            latest = self.document_status(library_id, document_id)
            status = latest.get("process_status")
            if status in DONE_STATUSES:
                return latest
            if status in FAILED_STATUSES:
                raise HTTPException(status_code=422, detail=latest)
            time.sleep(poll_seconds)
        raise HTTPException(status_code=504, detail={"message": "Timed out waiting for Mistral processing.", "latest": latest})

    def chat(self, library_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "inputs": [
                {
                    "type": "message.input",
                    "role": message["role"],
                    "content": message["content"],
                }
                for message in messages
            ],
            "instructions": (
                "Answer using the uploaded document library. If the document does not contain the answer, "
                "say so clearly and avoid guessing. Include the key figures when the user asks for metrics."
            ),
            "tools": [{"type": "document_library", "library_ids": [library_id]}],
            "completion_args": {"temperature": 0.2},
        }
        response = self._request("POST", "/conversations", json=payload)
        self._save_last_response(response)
        return response

    def chat_completions_fallback(self, library_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Answer using the uploaded document library. If the document does not contain the answer, "
                        "say so clearly and avoid guessing."
                    ),
                },
                *messages,
            ],
            "tools": [
                {
                    "type": "document_library",
                    "library_ids": [library_id],
                }
            ],
            "tool_choice": "auto",
            "temperature": 0.2,
        }
        response = self._request("POST", "/chat/completions", json=payload)
        self._save_last_response(response)
        return response

    def _save_last_response(self, response: dict[str, Any]) -> None:
        import json

        (data_root() / "last_mistral_response.json").write_text(
            json.dumps(response, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
