"""Minimal FastAPI surface for standalone card preview rendering."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import FastAPI

from .database import CardDatabase, DEFAULT_DB_PATH
from .preview import build_preview_payload


app = FastAPI(title="Armenian Cards API", version="0.1.0")


class PreviewRequest(BaseModel):
    source_deck: str | None = None
    db_path: str | None = None


@app.post("/cards/preview")
def cards_preview(req: PreviewRequest) -> dict:
    db = CardDatabase(req.db_path or DEFAULT_DB_PATH)
    return build_preview_payload(db, source_deck=req.source_deck)
