from __future__ import annotations

import re
from enum import StrEnum


class Intent(StrEnum):
    CHAT = "chat"
    TRANSLATION = "translation"
    DOCUMENT_QA = "document_qa"
    STUDY = "study"
    SPEECH = "speech"


class IntentRouter:
    """Conservative deterministic router; uncertain input stays in chat."""

    _patterns = {
        Intent.TRANSLATION: (r"\btranslate\b", r"\b(hindura|sobanura mu)\b"),
        Intent.DOCUMENT_QA: (r"\b(this|the|my) (file|document|pdf|notes)\b", r"\binyandiko\b"),
        Intent.STUDY: (r"\b(quiz|flashcards?|study notes?|teach me)\b", r"\b(ikizamini|nyigisha)\b"),
        Intent.SPEECH: (r"\b(transcribe|text to speech|read aloud)\b", r"\b(andika amajwi|soma uranguruye)\b"),
    }

    def classify(self, text: str, has_attachments: bool = False) -> Intent:
        normalized = " ".join(text.lower().split())
        if has_attachments and re.search(r"\b(ask|explain|summarize|document|file|notes)\b", normalized):
            return Intent.DOCUMENT_QA
        for intent, patterns in self._patterns.items():
            if any(re.search(pattern, normalized) for pattern in patterns):
                return intent
        return Intent.CHAT
