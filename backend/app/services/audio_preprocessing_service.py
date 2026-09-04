from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path

import numpy as np

from app.core.errors import AppError

AUDIO_TYPES = {
    "audio/wav": "wav", "audio/x-wav": "wav", "audio/mpeg": "mp3", "audio/mp3": "mp3",
    "audio/ogg": "ogg", "audio/webm": "webm", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
}


class AudioPreprocessingService:
    def validate(self, filename: str, content_type: str, content: bytes, max_bytes: int) -> str:
        if not content or len(content) > max_bytes:
            raise AppError("invalid_audio_size", f"Audio must be between 1 and {max_bytes} bytes", status_code=413)
        audio_type = AUDIO_TYPES.get(content_type.split(";", 1)[0].lower())
        if not audio_type:
            raise AppError("unsupported_audio_type", "Supported audio types are WAV, MP3, OGG, WebM, and M4A", status_code=415)
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in ({"mp3"} if audio_type == "mp3" else {audio_type}):
            raise AppError("audio_type_mismatch", "Filename extension does not match the audio type", status_code=415)
        signatures = {
            "wav": content.startswith((b"RIFF", b"RF64")), "mp3": content.startswith(b"ID3") or (len(content) > 1 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0),
            "ogg": content.startswith(b"OggS"), "webm": content.startswith(b"\x1aE\xdf\xa3"),
            "m4a": len(content) > 12 and content[4:8] == b"ftyp",
        }
        if not signatures[audio_type]:
            raise AppError("invalid_audio_signature", "Audio content does not match its declared type", status_code=415)
        return audio_type

    def _load_sync(self, content: bytes, suffix: str, sample_rate: int):
        import librosa
        with tempfile.NamedTemporaryFile(suffix=f".{suffix}", delete=False) as handle:
            handle.write(content)
            path = handle.name
        try:
            audio, rate = librosa.load(path, sr=sample_rate, mono=True)
        finally:
            Path(path).unlink(missing_ok=True)
        audio = audio.astype(np.float32)
        peak = np.max(np.abs(audio)) if len(audio) else 0
        if peak:
            audio /= peak
        try:
            import noisereduce as nr
            noise_length = min(int(rate * 0.5), len(audio))
            if noise_length:
                audio = nr.reduce_noise(y=audio, sr=rate, y_noise=audio[:noise_length], prop_decrease=0.7)
        except Exception:
            pass
        return audio.astype(np.float32), rate

    async def load(self, content: bytes, suffix: str, sample_rate: int = 16000):
        return await asyncio.to_thread(self._load_sync, content, suffix, sample_rate)
