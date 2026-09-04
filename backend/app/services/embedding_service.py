from __future__ import annotations

import asyncio
import threading

from app.core.config import Settings


class HuggingFaceEmbeddingService:
    dimensions = 768
    _model = None
    _tokenizer = None
    _lock = threading.Lock()

    def __init__(self, settings: Settings):
        self.model_name = settings.embedding_model
        if settings.embedding_dimensions != self.dimensions:
            raise ValueError(f"{self.model_name} requires {self.dimensions}-dimensional storage")

    @classmethod
    def _load(cls, model_name):
        if cls._model is None:
            from transformers import AutoModel, AutoTokenizer
            cls._tokenizer = AutoTokenizer.from_pretrained(model_name)
            cls._model = AutoModel.from_pretrained(model_name)
            cls._model.eval()
        return cls._tokenizer, cls._model

    def _embed_sync(self, texts: list[str], kind: str) -> list[list[float]]:
        import torch
        with self._lock:
            tokenizer, model = self._load(self.model_name)
            prefixed = [f"{kind}: {text}" for text in texts]
            batch = tokenizer(prefixed, max_length=512, padding=True, truncation=True, return_tensors="pt")
            with torch.no_grad():
                output = model(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1)
            pooled = (output * mask).sum(1) / mask.sum(1).clamp(min=1)
            normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
            return normalized.cpu().tolist()

    async def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_sync, texts, kind)
