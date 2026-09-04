from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass

from app.core.config import Settings
from app.services.audio_preprocessing_service import AudioPreprocessingService
from app.services.language_detection_service import LanguageDetectionService


@dataclass
class TranscriptionResult:
    raw_text: str
    corrected_text: str
    language: str
    duration_seconds: float
    timestamps: list[dict]
    model: str


class WhisperModelRegistry:
    _processor = None
    _models = {}
    _lock = threading.Lock()

    @classmethod
    def get(cls, model_name: str):
        with cls._lock:
            if cls._processor is None:
                from transformers import WhisperProcessor
                cls._processor = WhisperProcessor.from_pretrained("openai/whisper-small")
            if model_name not in cls._models:
                from transformers import WhisperForConditionalGeneration
                import torch
                model = WhisperForConditionalGeneration.from_pretrained(model_name)
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model.to(device).eval()
                cls._models[model_name] = (model, device)
            return cls._processor, *cls._models[model_name]


class WhisperTranscriptionService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.audio = AudioPreprocessingService()

    @staticmethod
    def _max_new_tokens(model) -> int:
        """Leave room for Whisper's decoder start, language, and task tokens."""
        max_positions = getattr(model.config, "max_target_positions", 448)
        return max(1, min(440, max_positions - 8))

    def _transcribe_sync(self, audio, rate, language):
        import torch
        model_name = self.settings.whisper_english_model if language == "en" else self.settings.whisper_kinyarwanda_model
        processor, model, device = WhisperModelRegistry.get(model_name)
        chunk_samples, texts, timestamps = rate * 30, [], []
        for index, start in enumerate(range(0, len(audio), chunk_samples)):
            chunk = audio[start:start + chunk_samples]
            if len(chunk) < rate // 2:
                continue
            features = processor(chunk, sampling_rate=rate, return_tensors="pt").input_features.to(device)
            kwargs = {
                "language": "en" if language == "en" else "sw",
                "task": "transcribe",
                "max_new_tokens": self._max_new_tokens(model),
            }
            with torch.no_grad():
                ids = model.generate(features, **kwargs)
            text = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
            if text:
                texts.append(text)
                timestamps.append({"start": round(start / rate, 2), "end": round(min(start + chunk_samples, len(audio)) / rate, 2), "text": text})
        raw = " ".join(texts).strip()
        corrected = re.sub(r"\s+([.,!?;:])", r"\1", re.sub(r"\s+", " ", raw)).strip()
        if corrected:
            corrected = corrected[0].upper() + corrected[1:]
        return TranscriptionResult(raw, corrected, language, len(audio) / rate, timestamps, model_name)

    async def transcribe(self, content: bytes, suffix: str, language: str):
        audio, rate = await self.audio.load(content, suffix)
        if language == "auto":
            english = await asyncio.to_thread(self._transcribe_sync, audio, rate, "en")
            detected, confidence = LanguageDetectionService().detect(english.raw_text)
            if detected == "rw" and confidence >= 0.5:
                return await asyncio.to_thread(self._transcribe_sync, audio, rate, "rw")
            return english
        return await asyncio.to_thread(self._transcribe_sync, audio, rate, language)
