from __future__ import annotations

import re


class LanguageDetectionService:
    """Small deterministic English/Kinyarwanda detector with an honest fallback."""

    RW_WORDS = {
        "abakiriya", "amakuru", "ariko", "cyangwa", "igihe", "ikibazo", "ikinyarwanda",
        "kandi", "kubera", "muraho", "ndashaka", "ntabwo", "rero", "urakoze", "uyu",
        "yacu", "yego", "ndashimira", "gusobanura", "inyandiko", "umunyeshuri",
    }
    EN_WORDS = {
        "and", "are", "because", "can", "english", "for", "from", "hello", "is", "not",
        "please", "that", "the", "this", "thank", "to", "what", "with", "you", "your",
    }

    def detect(self, text: str) -> tuple[str, float]:
        words = re.findall(r"[a-zA-ZÀ-ÿ']+", text.lower())
        if not words:
            return "en", 0.0
        rw_score = sum(word in self.RW_WORDS for word in words)
        en_score = sum(word in self.EN_WORDS for word in words)
        if rw_score > en_score:
            return "rw", min(0.55 + 0.08 * rw_score, 0.95)
        if en_score > rw_score:
            return "en", min(0.55 + 0.08 * en_score, 0.95)
        # Kinyarwanda morphology provides a useful signal when common-word scores tie.
        rw_prefixes = sum(word.startswith(("umu", "aba", "iki", "ibi", "ubu", "ndi", "nza")) for word in words)
        return ("rw", 0.51) if rw_prefixes >= 2 else ("en", 0.35)
