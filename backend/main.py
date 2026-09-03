"""
Audio-to-Text / Text-to-Speech backend — refined version.

Key changes vs. the original:
1. PAUSE-BASED PARAGRAPHING
   Paragraph breaks are now derived from actual silence gaps in the audio
   (energy-based voice-activity detection), not from a fixed sentence count.
   This is what makes live transcription split into real paragraphs.

2. REAL TEXT CORRECTION
   English correction now uses LanguageTool (grammar + spelling) when the
   optional `language_tool_python` package is installed, instead of a fixed
   lookup table that can only fix words you've already anticipated.
   Kinyarwanda correction supports an optional external wordlist
   (rw_wordlist.txt) for edit-distance spell correction; the old table is
   kept only as a final fallback.

3. LLM-BASED REWRITE / SUMMARY (optional)
   If ANTHROPIC_API_KEY is set, /tts/rewrite-text and the summary generator
   call an LLM for genuine rewriting/summarization. If no key is present,
   everything degrades gracefully to the original rule-based logic — the
   app still runs with zero new dependencies configured.

4. VOICE CLONING TTS (XTTS-v2, optional)
   /tts/synthesize now accepts a voice_id. If Coqui TTS (XTTS-v2) is
   installed and a voice's sample_audio_path exists, that sample is used
   as a zero-shot voice-clone reference. Falls back to gTTS if XTTS isn't
   installed or no voice_id is given — nothing breaks if you haven't set
   up XTTS yet.

Everything else (auth, DB schema usage, endpoints, admin routes) is kept
intact from the original file so this is a drop-in replacement.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
import os

# XTTS-v2's audio backend (torchcodec) needs FFmpeg's shared libraries on the
# DLL search path on Windows — a plain FFmpeg install often only ships static
# binaries with no separate .dll files. Point at the bundled shared build
# before any torch/TTS import happens, if present, so this stays optional
# elsewhere (this project's own copy lives in backend/ffmpeg_shared/bin).
_FFMPEG_DLL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg_shared', 'bin')
if os.path.isdir(_FFMPEG_DLL_DIR):
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(_FFMPEG_DLL_DIR)
    os.environ['PATH'] = _FFMPEG_DLL_DIR + os.pathsep + os.environ.get('PATH', '')

import uuid
import base64
import asyncio
import importlib
from database import db
from config import Config
import re
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
from auth import authenticate_user, create_access_token, register_user, get_current_user, require_permission, log_activity, reset_user_password, change_user_password, ACCESS_TOKEN_EXPIRE_MINUTES, has_permission, send_email
from fastapi.responses import RedirectResponse
import httpx
import json
import warnings
import torch
import librosa
import numpy as np
from transformers import WhisperProcessor, WhisperForConditionalGeneration
from dotenv import load_dotenv

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    print("⚠️ nest_asyncio not available - install with: pip install nest_asyncio")

try:
    import noisereduce as nr
    NOISE_REDUCE_AVAILABLE = True
except ImportError:
    nr = None
    NOISE_REDUCE_AVAILABLE = False
    print("⚠️ noisereduce not available")

try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    signal = None
    SCIPY_AVAILABLE = False
    print("⚠️ scipy not available")

try:
    import soundfile as sf
    SF_AVAILABLE = True
except ImportError:
    sf = None
    SF_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE_TTS = True
except ImportError:
    PyPDF2 = None
    PDF_AVAILABLE_TTS = False
    print("⚠️ PyPDF2 not available - install with: pip install PyPDF2")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    Document = None
    DOCX_AVAILABLE = False
    print("⚠️ python-docx not available - install with: pip install python-docx")

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    Image = None
    pytesseract = None
    OCR_AVAILABLE = False
    print("⚠️ OCR not available - install with: pip install Pillow pytesseract")

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    print("✅ gTTS available for TTS (fallback engine)")
except ImportError:
    gTTS = None
    GTTS_AVAILABLE = False
    print("⚠️ gTTS not available - install with: pip install gTTS")

try:
    edge_tts = importlib.import_module("edge_tts")
    EDGE_TTS_AVAILABLE = True
    print("✅ Edge TTS available as a fallback engine")
except ImportError:
    edge_tts = None
    EDGE_TTS_AVAILABLE = False
    print("⚠️ Edge TTS not available - install with: pip install edge-tts")

# NEW: Coqui XTTS-v2 for zero-shot voice cloning.
# Loaded via huggingface_hub + the raw Xtts model class rather than
# TTS.api.TTS(...), which downloads through Coqui's own (unreliable/flaky)
# CDN — the HF Hub mirror (coqui/XTTS-v2) is resumable and far more stable.
try:
    XttsConfig = importlib.import_module("TTS.tts.configs.xtts_config").XttsConfig
    Xtts = importlib.import_module("TTS.tts.models.xtts").Xtts
    XTTS_AVAILABLE = True
    print("✅ Coqui TTS available (XTTS-v2 voice cloning)")
except (ImportError, AttributeError):
    XttsConfig = None
    Xtts = None
    XTTS_AVAILABLE = False
    print("⚠️ Coqui TTS not available - install with: pip install coqui-tts")

# NEW: LanguageTool for real English grammar/spell correction
try:
    language_tool_python = importlib.import_module("language_tool_python")
    LANGUAGETOOL_AVAILABLE = True
    print("✅ LanguageTool available for English correction")
except ImportError:
    language_tool_python = None
    LANGUAGETOOL_AVAILABLE = False
    print("⚠️ language_tool_python not available - install with: pip install language-tool-python")

# NEW: Anthropic SDK for optional LLM-based rewrite/summarization
try:
    anthropic = importlib.import_module("anthropic")
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_AVAILABLE = False

load_dotenv()
warnings.filterwarnings("ignore")

# ============================================
# CONFIGURATION
# ============================================

HF_TOKEN = os.getenv("HF_TOKEN", "")
if not HF_TOKEN:
    print("⚠️ HF_TOKEN not set in environment — set it in your .env file, do not hardcode it")

KINYARWANDA_MODEL_ID = "pacomesimon/whisper-small-rw"
ENGLISH_MODEL_ID = "openai/whisper-small"
PROCESSOR_ID = "openai/whisper-small"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_REWRITE_ENABLED = ANTHROPIC_AVAILABLE and bool(ANTHROPIC_API_KEY)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if LLM_REWRITE_ENABLED else None
if LLM_REWRITE_ENABLED:
    print("✅ LLM rewrite/summarization enabled (Anthropic API)")
else:
    print("⚠️ LLM rewrite disabled — set ANTHROPIC_API_KEY to enable real rewriting/summarization")

# TTS Directories
TTS_OUTPUT_DIR = "tts_outputs"
TTS_DOCS_DIR = "tts_documents"
TTS_VOICES_DIR = "tts_voices"
TTS_PRONUNCIATIONS_DIR = "tts_pronunciations"

os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
os.makedirs(TTS_DOCS_DIR, exist_ok=True)
os.makedirs(TTS_VOICES_DIR, exist_ok=True)
os.makedirs(TTS_PRONUNCIATIONS_DIR, exist_ok=True)

# ============================================
# LOAD MODELS
# ============================================

print("=" * 60)
print("🎙️ Loading Transcription Models...")
print("=" * 60)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🖥️ Device: {DEVICE.upper()}")

processor = WhisperProcessor.from_pretrained(PROCESSOR_ID)

print("Loading English model...")
english_model = WhisperForConditionalGeneration.from_pretrained(
    "openai/whisper-small",
    token=HF_TOKEN or None,
)
english_model.to(DEVICE)
english_model.eval()
print("✅ English model loaded")

print("Loading Kinyarwanda model...")
kinyarwanda_model = WhisperForConditionalGeneration.from_pretrained(
    KINYARWANDA_MODEL_ID,
    token=HF_TOKEN or None,
)
kinyarwanda_model.to(DEVICE)
kinyarwanda_model.eval()
print("✅ Kinyarwanda model loaded")

# NEW: Load XTTS-v2 once at startup (heavy — only load if available).
# Downloaded via huggingface_hub (resumable, cached under xtts_v2_model/)
# rather than TTS.api.TTS's own downloader.
XTTS_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xtts_v2_model')
xtts_model = None
xtts_config = None
if XTTS_AVAILABLE:
    try:
        print("Loading XTTS-v2 voice cloning model (downloads ~2GB on first run)...")
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id="coqui/XTTS-v2", local_dir=XTTS_MODEL_DIR)
        xtts_config = XttsConfig()
        xtts_config.load_json(os.path.join(XTTS_MODEL_DIR, "config.json"))
        xtts_model = Xtts.init_from_config(xtts_config)
        xtts_model.load_checkpoint(xtts_config, checkpoint_dir=XTTS_MODEL_DIR, eval=True)
        xtts_model.to(DEVICE)
        print("✅ XTTS-v2 loaded")
    except Exception as e:
        print(f"⚠️ Failed to load XTTS-v2: {e}")
        xtts_model = None
        xtts_config = None
        XTTS_AVAILABLE = False

print("=" * 60)

# ============================================
# ENHANCED DOCUMENT PROCESSOR
# ============================================

class DocumentProcessor:
    """Extracts text from various document types"""

    def extract_text(self, file_path: str, file_type: str) -> dict:
        try:
            if file_type == 'pdf':
                return self.extract_pdf(file_path)
            elif file_type == 'docx':
                return self.extract_docx(file_path)
            elif file_type in ['txt', 'text']:
                return self.extract_txt(file_path)
            elif file_type in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
                return self.extract_image(file_path)
            else:
                return {"success": False, "error": f"Unsupported file type: {file_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_pdf(self, file_path: str) -> dict:
        if not PDF_AVAILABLE_TTS:
            return {"success": False, "error": "PDF support not available"}
        try:
            text = ""
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if not text.strip():
                return {"success": False, "error": "No text extracted from PDF"}
            return {"success": True, "text": text.strip(), "pages": len(reader.pages)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_docx(self, file_path: str) -> dict:
        if not DOCX_AVAILABLE:
            return {"success": False, "error": "DOCX support not available"}
        try:
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            text = "\n".join(paragraphs)
            if not text.strip():
                return {"success": False, "error": "No text extracted from DOCX"}
            return {"success": True, "text": text.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_txt(self, file_path: str) -> dict:
        try:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    text = file.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='latin-1') as file:
                    text = file.read()
            if not text.strip():
                return {"success": False, "error": "File is empty"}
            return {"success": True, "text": text.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_image(self, file_path: str) -> dict:
        if not OCR_AVAILABLE:
            return {"success": False, "error": "OCR support not available"}
        try:
            image = Image.open(file_path)
            image = image.convert('L')
            try:
                # Kinyarwanda uses the Latin script, so this only helps if the
                # server has kin.traineddata installed alongside Tesseract —
                # falls back to English-only OCR if it isn't.
                text = pytesseract.image_to_string(image, lang='eng+kin')
            except Exception:
                text = pytesseract.image_to_string(image)
            if not text.strip():
                return {"success": False, "error": "No text detected in image"}
            return {"success": True, "text": text.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================
# NEW: PAUSE-BASED PARAGRAPH SEGMENTATION
# ============================================

class PauseParagraphSegmenter:
    """
    Detects real silence gaps in audio and uses them to decide where
    paragraph breaks belong — instead of guessing from sentence count.

    Works on the raw waveform, independent of chunking, so it applies the
    same way to a fully-uploaded file or to a rolling buffer from a live
    stream.
    """

    def __init__(self, min_pause_ms: int = 700, frame_ms: int = 20):
        self.min_pause_ms = min_pause_ms
        self.frame_ms = frame_ms

    def detect_pause_boundaries(self, audio_array: np.ndarray, sr: int) -> list:
        """Returns a list of (start_sample, end_sample) for silences >= min_pause_ms."""
        frame_len = max(1, int(sr * self.frame_ms / 1000))
        n_frames = max(1, (len(audio_array) - frame_len) // frame_len)
        if n_frames <= 0:
            return []

        energy = np.array([
            np.sqrt(np.mean(audio_array[i * frame_len:(i + 1) * frame_len] ** 2) + 1e-12)
            for i in range(n_frames)
        ])

        # Adaptive threshold — quieter of (15th percentile, a small absolute floor)
        silence_thresh = max(np.percentile(energy, 15), 1e-4)
        is_silent = energy < silence_thresh

        min_pause_frames = max(1, int(self.min_pause_ms / self.frame_ms))
        boundaries = []
        run_start = None
        for i, silent in enumerate(is_silent):
            if silent and run_start is None:
                run_start = i
            elif not silent and run_start is not None:
                if i - run_start >= min_pause_frames:
                    boundaries.append((run_start * frame_len, i * frame_len))
                run_start = None
        if run_start is not None and (n_frames - run_start) >= min_pause_frames:
            boundaries.append((run_start * frame_len, n_frames * frame_len))

        return boundaries

    def chunk_has_trailing_pause(self, boundaries: list, chunk_end_sample: int, tolerance_samples: int) -> bool:
        """True if a detected silence starts within `tolerance_samples` of this chunk's end."""
        for start, end in boundaries:
            if abs(start - chunk_end_sample) <= tolerance_samples:
                return True
        return False


pause_segmenter = PauseParagraphSegmenter(min_pause_ms=700)


# ============================================
# TEXT CORRECTION — ENGLISH (LanguageTool-backed)
# ============================================

class EnglishTextCorrector:
    """
    Uses LanguageTool for real grammar/spelling correction when available.
    Falls back to a small manual lookup table (kept from the original code)
    for cases LanguageTool won't catch, such as ASR-specific mis-hearings
    (e.g. 'wanked' -> 'worked').
    """

    _tool = None
    _tool_init_failed = False

    # ASR-specific mishearings LanguageTool has no way to know about.
    # Keep this list small and specific to your models' actual failure modes.
    asr_specific_corrections = {
        'wanked': 'worked', 'wank': 'work', 'wanking': 'working',
        'be come': 'become', 'puer': 'poor', 'poer': 'poor',
        'notize': 'noticed', 'teurer': 'teacher', 'straddard': 'studied',
        'triated': 'treated', 'castoma': 'customer', 'admiret': 'admired',
        'chazing': 'chasing',
    }

    @classmethod
    def _get_tool(cls):
        if cls._tool is not None or cls._tool_init_failed:
            return cls._tool
        if not LANGUAGETOOL_AVAILABLE:
            cls._tool_init_failed = True
            return None
        try:
            cls._tool = language_tool_python.LanguageTool('en-US')
        except Exception as e:
            print(f"⚠️ LanguageTool failed to start: {e}")
            cls._tool_init_failed = True
            cls._tool = None
        return cls._tool

    def _apply_asr_corrections(self, text: str) -> str:
        words = text.split()
        out = []
        for word in words:
            clean = word.strip('.,!?;:()"\'')
            punct = word[len(clean):] if len(word) > len(clean) else ''
            if clean.lower() in self.asr_specific_corrections:
                corrected = self.asr_specific_corrections[clean.lower()]
                if clean[:1].isupper():
                    corrected = corrected.capitalize()
                out.append(corrected + punct)
            else:
                out.append(word)
        return ' '.join(out)

    def correct_text(self, text: str) -> str:
        if not text:
            return text

        text = self._apply_asr_corrections(text)

        tool = self._get_tool()
        if tool is not None:
            try:
                matches = tool.check(text)
                text = language_tool_python.utils.correct(text, matches)
            except Exception as e:
                print(f"⚠️ LanguageTool correction failed, keeping ASR-corrected text: {e}")

        # Normalize spacing / punctuation / capitalization
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'([.!?])\s*([A-Za-z])', r'\1 \2', text)
        sentences = re.split(r'([.!?]+\s+)', text)
        for i in range(0, len(sentences), 2):
            if sentences[i].strip():
                sentences[i] = sentences[i][0].upper() + sentences[i][1:] if len(sentences[i]) > 1 else sentences[i].upper()
        text = ''.join(sentences)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


# ============================================
# TEXT CORRECTION — KINYARWANDA
# ============================================

class KinyarwandaTextCorrector:
    """
    Kinyarwanda has no mature LanguageTool-style grammar checker, so this
    supports an optional external wordlist (rw_wordlist.txt, one word per
    line — e.g. exported from Mozilla Common Voice Kinyarwanda transcripts)
    for edit-distance spell correction. Falls back to punctuation/casing
    cleanup only if no wordlist is configured — it no longer pretends to
    "correct" words by mapping them to themselves.
    """

    def __init__(self, wordlist_path: str = "rw_wordlist.txt"):
        self.vocab = set()
        if os.path.exists(wordlist_path):
            with open(wordlist_path, 'r', encoding='utf-8') as f:
                self.vocab = {line.strip().lower() for line in f if line.strip()}
            print(f"✅ Loaded {len(self.vocab)} Kinyarwanda words for spell correction")
        else:
            print(f"⚠️ No Kinyarwanda wordlist at {wordlist_path} — spell correction disabled, "
                  f"only punctuation/casing cleanup will run. Export word frequencies from "
                  f"Common Voice Kinyarwanda transcripts to enable this.")

    def _closest_word(self, word: str, max_distance: int = 2) -> Optional[str]:
        if not self.vocab or word.lower() in self.vocab:
            return None
        best, best_dist = None, max_distance + 1
        wl = word.lower()
        for candidate in self.vocab:
            if abs(len(candidate) - len(wl)) > max_distance:
                continue
            dist = self._levenshtein(wl, candidate)
            if dist < best_dist:
                best, best_dist = candidate, dist
        return best if best_dist <= max_distance else None

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        if len(a) < len(b):
            a, b = b, a
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            curr = [i]
            for j, cb in enumerate(b, 1):
                curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = curr
        return prev[-1]

    def correct_text(self, text: str) -> str:
        if not text:
            return text

        if self.vocab:
            words = text.split()
            corrected = []
            for word in words:
                clean = word.strip('.,!?;:()"\'')
                punct = word[len(clean):] if len(word) > len(clean) else ''
                suggestion = self._closest_word(clean)
                corrected.append((suggestion if suggestion else clean) + punct)
            text = ' '.join(corrected)

        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)

        sentences = re.split(r'([.!?]+\s+)', text)
        for i in range(0, len(sentences), 2):
            if sentences[i].strip():
                sentences[i] = sentences[i][0].upper() + sentences[i][1:] if len(sentences[i]) > 1 else sentences[i].upper()
        text = ''.join(sentences)

        return text.strip()


kinyarwanda_corrector = KinyarwandaTextCorrector()
english_corrector = EnglishTextCorrector()


# ============================================
# NEW: LLM-BASED REWRITE / SUMMARIZATION (optional)
# ============================================

def llm_rewrite_text(text: str, language: str = 'en') -> Optional[str]:
    """Returns an LLM rewrite of `text`, or None if the LLM isn't configured/failed."""
    if not LLM_REWRITE_ENABLED or not text.strip():
        return None
    lang_label = "Kinyarwanda" if language == 'rw' else "English"
    try:
        resp = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": (
                    f"Rewrite the following {lang_label} transcript to fix grammar, spelling, "
                    f"punctuation and paragraphing, without changing its meaning or adding content. "
                    f"Return only the corrected text, nothing else:\n\n{text}"
                )
            }]
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    except Exception as e:
        print(f"⚠️ LLM rewrite failed: {e}")
        return None


def llm_summarize_text(text: str, language: str = 'en') -> Optional[dict]:
    """Returns {'summary': str} from the LLM, or None if unavailable/failed."""
    if not LLM_REWRITE_ENABLED or not text.strip():
        return None
    lang_label = "Kinyarwanda" if language == 'rw' else "English"
    try:
        resp = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": (
                    f"Write a concise, faithful summary of this {lang_label} transcript in the same "
                    f"language. Return only the summary text:\n\n{text}"
                )
            }]
        )
        summary = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        return {"summary": summary} if summary else None
    except Exception as e:
        print(f"⚠️ LLM summarization failed: {e}")
        return None


# ============================================
# PRONUNCIATION LEARNING SYSTEM
# ============================================

class PronunciationLearner:
    def __init__(self):
        self.pronunciation_db = {}
        self.load_pronunciation_db()

    def load_pronunciation_db(self):
        db_path = os.path.join(TTS_PRONUNCIATIONS_DIR, "pronunciation_db.json")
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    self.pronunciation_db = json.load(f)
                print(f"✅ Loaded {len(self.pronunciation_db)} pronunciations")
            except Exception:
                self.pronunciation_db = {}

    def save_pronunciation_db(self):
        db_path = os.path.join(TTS_PRONUNCIATIONS_DIR, "pronunciation_db.json")
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(self.pronunciation_db, f, ensure_ascii=False, indent=2)

    def learn_pronunciation(self, word: str, audio_path: str, transcript: str) -> dict:
        word = word.lower().strip()
        duration = 0
        try:
            duration = librosa.get_duration(filename=audio_path)
        except Exception:
            pass

        if word not in self.pronunciation_db:
            self.pronunciation_db[word] = []

        entry = {
            "word": word,
            "audio_path": audio_path,
            "transcript": transcript,
            "duration": duration,
            "created_at": datetime.now().isoformat(),
            "source": "user_recording"
        }
        self.pronunciation_db[word].append(entry)
        self.save_pronunciation_db()

        return {"success": True, "word": word, "pronunciations": len(self.pronunciation_db[word])}

    def get_pronunciation(self, word: str) -> Optional[dict]:
        word = word.lower().strip()
        if word in self.pronunciation_db and self.pronunciation_db[word]:
            return self.pronunciation_db[word][-1]
        return None


pronunciation_learner = PronunciationLearner()

# ============================================
# HELPER FUNCTIONS
# ============================================

def split_text_into_chunks(text: str, max_chars: int = 5000) -> list:
    if not text:
        return []
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(current_chunk) + len(paragraph) < max_chars:
            current_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = paragraph
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def combine_audio_files(audio_paths: list) -> str:
    if len(audio_paths) <= 1:
        return audio_paths[0] if audio_paths else None
    try:
        audio_data = []
        sample_rate = 16000
        for path in audio_paths:
            if os.path.exists(path):
                audio, sr = librosa.load(path, sr=sample_rate)
                audio_data.append(audio)
        if not audio_data:
            return audio_paths[0]
        combined = np.concatenate(audio_data)
        output_path = os.path.join(TTS_OUTPUT_DIR, f"combined_{uuid.uuid4()}.wav")
        if SF_AVAILABLE and sf:
            sf.write(output_path, combined, sample_rate)
        for path in audio_paths:
            if os.path.exists(path) and path != output_path:
                try:
                    os.remove(path)
                except Exception:
                    pass
        return output_path
    except Exception as e:
        print(f"Error combining audio: {e}")
        return audio_paths[0] if audio_paths else None


# ============================================
# CREATE FASTAPI APP
# ============================================

app = FastAPI(title="EVA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIO_DIR = "stored_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(Config.TEMP_DIR, exist_ok=True)

# ============================================
# PDF EXPORT
# ============================================

PDF_AVAILABLE = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    PDF_AVAILABLE = True
    print("✅ PDF export available")
except Exception:
    print("⚠️ PDF export not available")

# ============================================
# MODELS
# ============================================

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    provider: Optional[str] = "email"


class PasswordResetRequest(BaseModel):
    identifier: str
    new_password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


def post_process_kinyarwanda(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
    return text.strip()


# ============================================
# AUDIO PREPROCESSING
# ============================================

def preprocess_audio(audio: np.ndarray, sr: int) -> np.ndarray:
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)

    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val

    if SCIPY_AVAILABLE and signal is not None:
        try:
            nyquist = sr / 2
            sos = signal.butter(4, [80 / nyquist, 7600 / nyquist], btype='band', output='sos')
            audio = signal.sosfilt(sos, audio)
        except Exception:
            pass

    if NOISE_REDUCE_AVAILABLE and nr is not None:
        try:
            noise_sample_len = min(int(sr * 0.5), len(audio))
            if noise_sample_len > 0:
                noise_sample = audio[:noise_sample_len]
                audio = nr.reduce_noise(y=audio, sr=sr, y_noise=noise_sample, prop_decrease=0.7)
        except Exception:
            pass

    return audio.astype(np.float32)


def load_audio(file_path: str, target_sr: int = 16000) -> tuple:
    audio, sr = librosa.load(file_path, sr=target_sr, mono=True)
    audio = audio.astype(np.float32)
    audio = preprocess_audio(audio, sr)
    return audio, sr


# ============================================
# TRANSCRIPTION (with pause-based paragraphing)
# ============================================

def transcribe_audio(file_path: str, language_code: str) -> dict:
    start_time = datetime.now()

    audio_array, sr = load_audio(file_path, target_sr=16000)
    total_duration_seconds = len(audio_array) / sr
    print(f"📊 Audio duration: {total_duration_seconds:.1f} seconds")

    model_to_use = english_model if language_code == 'en' else kinyarwanda_model
    print(f"🎤 Using {'English' if language_code == 'en' else 'Kinyarwanda'} model")

    # Detect real pauses once, up front — used to decide paragraph breaks
    pause_boundaries = pause_segmenter.detect_pause_boundaries(audio_array, sr)
    print(f"🔇 Detected {len(pause_boundaries)} pause(s) ≥700ms")

    CHUNK_DURATION = 15
    OVERLAP_DURATION = 3.5
    samples_per_chunk = int(CHUNK_DURATION * sr)
    overlap_samples = int(OVERLAP_DURATION * sr)
    stride = samples_per_chunk - overlap_samples

    chunk_spans = []  # (start_sample, end_sample)
    start_sample = 0
    while start_sample < len(audio_array):
        end_sample = min(start_sample + samples_per_chunk, len(audio_array))
        chunk = audio_array[start_sample:end_sample]
        if len(chunk) >= sr * 2:
            chunk_spans.append((start_sample, end_sample))
        start_sample += stride

    if not chunk_spans:
        chunk_spans = [(0, len(audio_array))]

    print(f"📦 Processing {len(chunk_spans)} chunks")

    all_text_parts = []
    tolerance = int(sr * 0.5)  # 500ms tolerance when matching pause to chunk boundary

    for idx, (cs, ce) in enumerate(chunk_spans):
        print(f"  Processing chunk {idx + 1}/{len(chunk_spans)}...")
        chunk = audio_array[cs:ce]

        inputs = processor(chunk, sampling_rate=16000, return_tensors="pt")
        input_features = inputs.input_features.to(DEVICE)

        with torch.no_grad():
            if language_code == 'en':
                generate_kwargs = {
                    "max_new_tokens": 256, "temperature": 0.0,
                    "repetition_penalty": 1.2, "no_repeat_ngram_size": 3,
                    "language": "en", "task": "transcribe"
                }
            else:
                # pacomesimon/whisper-small-rw was fine-tuned from
                # mbazaNLP/Whisper-Small-Kinyarwanda, which repurposes Whisper's
                # Swahili ('sw') language token as the Kinyarwanda prompt — the
                # model card documents this as required for correct decoding.
                generate_kwargs = {
                    "max_new_tokens": 256, "temperature": 0.0,
                    "repetition_penalty": 1.1, "no_repeat_ngram_size": 3,
                    "language": "sw", "task": "transcribe"
                }
            predicted_ids = model_to_use.generate(input_features, **generate_kwargs)

        chunk_text = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
        if chunk_text:
            # NEW: decide the separator based on whether a real pause follows this chunk
            is_paragraph_break = pause_segmenter.chunk_has_trailing_pause(pause_boundaries, ce, tolerance)
            all_text_parts.append((chunk_text, is_paragraph_break))

    # Assemble text using real pause boundaries for paragraph breaks
    full_text = ""
    for i, (chunk_text, is_break) in enumerate(all_text_parts):
        if i == 0:
            full_text = chunk_text
        else:
            separator = "\n\n" if is_break else " "
            full_text += separator + chunk_text

    if full_text:
        full_text = re.sub(r'[ \t]+', ' ', full_text)
        full_text = re.sub(r'[ \t]+([.,!?;:])', r'\1', full_text)
        full_text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', full_text)

    if language_code == 'en' and full_text:
        full_text = english_corrector.correct_text(full_text)
    elif full_text:
        full_text = kinyarwanda_corrector.correct_text(full_text)

    processing_time = (datetime.now() - start_time).total_seconds()
    word_count = len(full_text.split()) if full_text else 0
    print(f"✅ Transcription complete: {len(full_text)} chars, {word_count} words")

    return {
        "text": full_text if full_text else "",
        "duration": processing_time,
        "duration_seconds": total_duration_seconds,
        "chunks_processed": len(chunk_spans),
        "paragraph_breaks_detected": sum(1 for _, b in all_text_parts if b),
        "language_used": language_code
    }


# ============================================
# TRANSLATION (English <-> Kinyarwanda, NLLB-200)
# ============================================
# Local, open-source model — no API key, no per-request cost. Argos Translate /
# LibreTranslate don't cover Kinyarwanda at all, and free translation APIs
# (e.g. MyMemory) fail silently for this language pair, so NLLB-200 is the
# only free option that actually supports it (as `kin_Latn`).

NLLB_MODEL_NAME = "facebook/nllb-200-distilled-600M"
NLLB_LANG_CODES = {"en": "eng_Latn", "rw": "kin_Latn"}

_nllb_tokenizer = None
_nllb_model = None


def _get_nllb():
    """Lazily load the NLLB-200 model on first translation request."""
    global _nllb_tokenizer, _nllb_model
    if _nllb_model is None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        print(f"📥 Loading translation model ({NLLB_MODEL_NAME})... this only happens once")
        _nllb_tokenizer = AutoTokenizer.from_pretrained(NLLB_MODEL_NAME)
        _nllb_model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL_NAME).to(DEVICE)
        _nllb_model.eval()
        print("✅ Translation model loaded")
    return _nllb_tokenizer, _nllb_model


def _split_into_segments(text: str, max_chars: int = 400) -> List[str]:
    """Split long text into paragraph/sentence-sized segments so translation
    quality doesn't degrade from truncating a single huge input."""
    paragraphs = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
    segments = []
    for para in paragraphs:
        if len(para) <= max_chars:
            segments.append(para)
            continue
        sentences = re.split(r'(?<=[.!?])\s+', para)
        current = ""
        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > max_chars:
                segments.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            segments.append(current)
    return segments or [text]


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    if source_lang not in NLLB_LANG_CODES or target_lang not in NLLB_LANG_CODES:
        raise ValueError(f"Unsupported language pair: {source_lang} -> {target_lang}")
    if not text or not text.strip():
        return ""

    tokenizer, model = _get_nllb()
    tokenizer.src_lang = NLLB_LANG_CODES[source_lang]
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(NLLB_LANG_CODES[target_lang])

    translated_segments = []
    for segment in _split_into_segments(text):
        inputs = tokenizer(segment, return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=512,
                num_beams=4,
            )
        translated_segments.append(tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip())

    # Rejoin using the same paragraph structure the input had
    original_paragraphs = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
    if len(original_paragraphs) == len(translated_segments):
        return '\n\n'.join(translated_segments)
    return ' '.join(translated_segments)


def get_word_count(text: str) -> int:
    return len(text.split())


def split_into_sentences(text: str, words_per_pseudo_sentence: int = 16) -> list:
    """Split text into sentence-like units for summarization/key-point scoring.

    Some sources (browser speech-recognition APIs on unsupported locales,
    certain ASR engines) never emit sentence punctuation at all — splitting
    on `[.!?]+` alone then returns the ENTIRE text as one "sentence", which
    collapses summaries and key points into a single giant blob. When that
    happens, fall back to paragraph breaks (real pause boundaries, if
    present) and then fixed-size word chunks, so downstream scoring always
    has real units to work with.
    """
    raw = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    if len(raw) > 1:
        return raw

    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()] or [text]
    chunks = []
    for para in paragraphs:
        words = para.split()
        for i in range(0, len(words), words_per_pseudo_sentence):
            chunk = ' '.join(words[i:i + words_per_pseudo_sentence])
            if chunk:
                chunks.append(chunk)
    return chunks or raw


def format_text_to_paragraphs(text: str, language: str = 'en') -> str:
    """
    Fallback formatter for text that didn't come from transcribe_audio
    (e.g. manually saved speech recordings) and therefore has no
    pause-derived breaks yet. Still sentence-count based, but only used
    as a last resort now.
    """
    if not text:
        return text
    if '\n\n' in text:
        return text  # already has real paragraph breaks — don't override them

    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        # No real sentence punctuation to split on (e.g. raw speech-recognition
        # output) — fall back to fixed-size word chunks instead of dumping
        # the whole transcript into a single paragraph.
        sentences = split_into_sentences(text)
    if not sentences:
        return text

    total_sentences = len(sentences)
    if total_sentences <= 5:
        sentences_per_paragraph = total_sentences
    elif total_sentences <= 12:
        sentences_per_paragraph = 3
    elif total_sentences <= 25:
        sentences_per_paragraph = 4
    else:
        sentences_per_paragraph = 5

    paragraphs = []
    for i in range(0, total_sentences, sentences_per_paragraph):
        paragraph = ' '.join(sentences[i:i + sentences_per_paragraph])
        if paragraph and paragraph[-1] not in '.!?':
            paragraph += '.'
        paragraphs.append(paragraph)

    return '\n\n'.join(paragraphs)


# ============================================
# SUMMARY GENERATION (LLM-first, extractive fallback)
# ============================================

def generate_smart_summary(text: str, audio_duration_seconds: float = None, language: str = 'en') -> dict:
    if not text or len(text.strip()) < 20:
        return {"summary": text if text else "No content to summarize", "compression": "0%",
                "original_words": 0, "summary_words": 0, "type": "none", "target_percent": 0}

    llm_result = llm_summarize_text(text, language)
    if llm_result:
        original_word_count = get_word_count(text)
        summary_word_count = get_word_count(llm_result["summary"])
        compression = f"{int((summary_word_count / max(original_word_count, 1)) * 100)}%"
        return {
            "summary": llm_result["summary"],
            "original_words": original_word_count,
            "summary_words": summary_word_count,
            "compression": compression,
            "type": "llm_summary",
            "target_percent": summary_word_count * 100 // max(original_word_count, 1)
        }

    # --- Extractive fallback (original logic, unchanged) ---
    sentences = [s for s in split_into_sentences(text) if len(s) > 5]
    if not sentences:
        return {"summary": text[:300], "compression": "100%", "original_words": get_word_count(text),
                "summary_words": get_word_count(text[:300]), "type": "truncated", "target_percent": 100}

    original_word_count = get_word_count(text)
    total_sentences = len(sentences)

    if audio_duration_seconds:
        if audio_duration_seconds < 30:
            target_percent, summary_type = 0.70, "full_summary"
        elif audio_duration_seconds < 60:
            target_percent, summary_type = 0.55, "detailed_summary"
        elif audio_duration_seconds < 180:
            target_percent, summary_type = 0.42, "standard_summary"
        elif audio_duration_seconds < 600:
            target_percent, summary_type = 0.35, "concise_summary"
        elif audio_duration_seconds < 1800:
            target_percent, summary_type = 0.28, "executive_summary"
        else:
            target_percent, summary_type = 0.22, "ultra_summary"
    else:
        target_percent, summary_type = 0.35, "standard_summary"

    target_count = max(2, min(20, int(total_sentences * target_percent)))

    scored_sentences = []
    for idx, sentence in enumerate(sentences):
        score = 0
        if idx < 2:
            score += 3
        elif idx < 5:
            score += 1.5
        elif idx > total_sentences - 3:
            score += 2.5
        elif idx > total_sentences - 6:
            score += 1

        word_len = len(sentence.split())
        if 12 <= word_len <= 35:
            score += 2
        elif 35 < word_len <= 50:
            score += 1
        elif word_len < 8:
            score -= 1

        important_keywords = ['important', 'significant', 'key', 'essential', 'critical',
                               'main', 'primary', 'conclusion', 'therefore', 'thus',
                               'result', 'finally', 'consequently']
        for kw in important_keywords:
            if kw.lower() in sentence.lower():
                score += 1.2
                break

        if re.search(r'\d+', sentence):
            score += 0.8
        scored_sentences.append((score, sentence, idx))

    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    selected_indices = set()
    selected_sentences = []

    for i in range(min(2, total_sentences)):
        if i not in selected_indices:
            selected_indices.add(i)
            selected_sentences.append(sentences[i])

    for i in range(max(0, total_sentences - 2), total_sentences):
        if i not in selected_indices:
            selected_indices.add(i)
            selected_sentences.append(sentences[i])

    remaining = target_count - len(selected_indices)
    for score, sentence, idx in scored_sentences:
        if idx not in selected_indices and remaining > 0:
            selected_indices.add(idx)
            selected_sentences.append(sentence)
            remaining -= 1

    selected_sentences.sort(key=lambda x: sentences.index(x))
    summary = '. '.join(selected_sentences) + '.'
    summary = re.sub(r'\s+', ' ', summary)
    summary = re.sub(r'\.\.+', '.', summary)

    summary_word_count = get_word_count(summary)
    compression = f"{int((summary_word_count / original_word_count) * 100)}%"

    return {
        "summary": summary,
        "original_words": original_word_count,
        "summary_words": summary_word_count,
        "compression": compression,
        "type": summary_type,
        "target_percent": int(target_percent * 100)
    }


def extract_smart_key_points(text: str, audio_duration_seconds: float = None) -> list:
    if not text:
        return []

    if audio_duration_seconds:
        if audio_duration_seconds < 60:
            num_points = 3
        elif audio_duration_seconds < 180:
            num_points = 4
        elif audio_duration_seconds < 600:
            num_points = 5
        elif audio_duration_seconds < 1800:
            num_points = 7
        else:
            num_points = 10
    else:
        num_points = 5

    sentences = [s for s in split_into_sentences(text) if len(s) > 15]
    if not sentences:
        sentences = [s for s in split_into_sentences(text) if len(s) > 8]
    if not sentences:
        return [{"number": 1, "text": text[:150] + "...", "importance": "medium", "icon": "🟡"}]

    scored_sentences = []
    for idx, s in enumerate(sentences[:30]):
        score = 0
        if idx == 0:
            score += 3
        elif idx == len(sentences[:30]) - 1:
            score += 2.5
        elif idx < 3:
            score += 2
        elif idx > len(sentences[:30]) - 4:
            score += 1.5

        word_len = len(s.split())
        if 12 <= word_len <= 30:
            score += 2
        elif 30 < word_len <= 45:
            score += 1
        elif word_len > 50:
            score -= 0.5

        important_keywords = ['important', 'significant', 'key', 'essential', 'critical',
                               'main', 'conclusion', 'therefore', 'thus', 'result', 'finally']
        for kw in important_keywords:
            if kw.lower() in s.lower():
                score += 1.5
                break

        if re.search(r'\d+', s):
            score += 1
        scored_sentences.append((score, s))

    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    selected = []
    seen_texts = set()
    for score, s in scored_sentences[:num_points * 2]:
        s_lower = s.lower()[:50]
        if s_lower not in seen_texts and len(selected) < num_points:
            seen_texts.add(s_lower)
            selected.append(s)

    points = []
    for i, s in enumerate(selected):
        if i == 0:
            importance, icon = "high", "🔴"
        elif i <= 2:
            importance, icon = "medium", "🟡"
        else:
            importance, icon = "low", "🟢"
        points.append({"number": i + 1, "text": s, "importance": importance, "icon": icon})

    return points


# ============================================
# TTS FUNCTIONS
# ============================================

def synthesize_with_gtts(text: str, language: str = 'rw') -> dict:
    if not GTTS_AVAILABLE:
        return {"success": False, "error": "gTTS not available"}
    try:
        # gTTS has no native Kinyarwanda voice. Swahili is the closest
        # supported regional fallback and, unlike the invalid `rw` code,
        # reliably produces playable audio.
        lang_code = 'sw' if language == 'rw' else 'en'
        filename = f"tts_{uuid.uuid4()}.mp3"
        output_path = os.path.join(TTS_OUTPUT_DIR, filename)

        tts = gTTS(text=text, lang=lang_code, slow=False)
        tts.save(output_path)

        duration = 0
        try:
            duration = librosa.get_duration(filename=output_path)
        except Exception:
            pass

        return {
            "success": True, "audio_path": output_path,
            "audio_url": f"/tts/audio/{filename}", "duration": duration,
            "filename": filename,
            "engine": "gtts_swahili_fallback" if language == 'rw' else "gtts"
        }
    except Exception as e:
        print(f"⚠️ gTTS synthesis failed: {e}")
        return {"success": False, "error": str(e)}


# Real edge-tts voices for the languages we support (verified against the
# live `edge_tts.list_voices()` catalog — do not add names without checking,
# a wrong ShortName just fails synthesis). Kinyarwanda has no native cloud
# voice, so it's proxied through Swahili, which only has 2 real actors per
# gender (Tanzania/Kenya) and no genuine child/elderly/teen variety. Rather
# than silently reusing one identical voice for every persona, non-adult
# personas alternate to the other regional accent so picking a different
# persona is at least audibly a different voice — it is NOT a true age
# simulation, and 'celebrity' has no real backing voice at all (no celebrity
# voice mimicry is implemented, intentionally, since that would require
# cloning a real person's voice without consent).
EDGE_VOICE_MAP = {
    'rw': {
        'female': 'sw-TZ-RehemaNeural', 'male': 'sw-TZ-DaudiNeural',
        'elderly_female': 'sw-TZ-RehemaNeural', 'elderly_male': 'sw-TZ-DaudiNeural',
        'teenage_female': 'sw-KE-ZuriNeural', 'teenage_male': 'sw-KE-RafikiNeural',
        'child': 'sw-KE-ZuriNeural', 'celebrity': 'sw-TZ-RehemaNeural',
    },
    'en': {
        'female': 'en-US-JennyNeural', 'male': 'en-US-GuyNeural',
        'elderly_female': 'en-US-MichelleNeural', 'elderly_male': 'en-US-ChristopherNeural',
        'teenage_female': 'en-US-AriaNeural', 'teenage_male': 'en-US-RogerNeural',
        'child': 'en-US-AnaNeural', 'celebrity': 'en-US-JennyNeural',
    },
}


def pick_edge_voice(language: str, gender: Optional[str]) -> str:
    lang_map = EDGE_VOICE_MAP.get(language, EDGE_VOICE_MAP['en'])
    return lang_map.get(gender, lang_map['female'])


async def synthesize_with_edge_tts(text: str, language: str = 'rw', voice: Optional[str] = None) -> dict:
    """Generate audio with Edge TTS when Google TTS is unavailable."""
    if not EDGE_TTS_AVAILABLE:
        return {"success": False, "error": "Edge TTS is not available"}

    if not voice:
        # Kinyarwanda has no native voice in the bundled cloud engines; use the
        # closest regional Swahili voice rather than the unsupported `rw` locale.
        voice = "sw-TZ-RehemaNeural" if language == "rw" else "en-US-AriaNeural"
    filename = f"tts_{uuid.uuid4()}.mp3"
    output_path = os.path.join(TTS_OUTPUT_DIR, filename)
    try:
        await edge_tts.Communicate(text, voice=voice).save(output_path)
        duration = 0
        try:
            duration = librosa.get_duration(filename=output_path)
        except Exception:
            pass
        return {
            "success": True, "audio_path": output_path,
            "audio_url": f"/tts/audio/{filename}", "duration": duration,
            "filename": filename,
            "engine": "edge_tts_swahili_fallback" if language == "rw" else "edge_tts"
        }
    except Exception as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        print(f"⚠️ Edge TTS synthesis failed: {e}")
        return {"success": False, "error": f"gTTS failed and Edge TTS failed: {e}"}


def synthesize_with_xtts(text: str, language: str, speaker_wav_path: str) -> dict:
    """
    NEW: Zero-shot voice cloning synthesis. Given a short reference sample of a
    voice (the one saved in voice_models.sample_audio_path), XTTS-v2 generates
    speech in that voice/timbre without any per-user training.

    Note: XTTS-v2 does not include Kinyarwanda in its trained language set, so
    'rw' requests are synthesized with the closest supported setting and will
    carry an accent. True Kinyarwanda-native TTS needs a Kinyarwanda-trained
    model (e.g. Piper/VITS on Common Voice Kinyarwanda) — XTTS solves voice
    cloning, not language coverage.
    """
    if not XTTS_AVAILABLE or xtts_model is None:
        return {"success": False, "error": "XTTS not available"}
    if not speaker_wav_path or not os.path.exists(speaker_wav_path):
        return {"success": False, "error": "Speaker reference audio not found"}

    xtts_lang = "en"  # closest supported language; see note above for 'rw'
    try:
        filename = f"tts_xtts_{uuid.uuid4()}.wav"
        output_path = os.path.join(TTS_OUTPUT_DIR, filename)

        result = xtts_model.synthesize(
            text,
            xtts_config,
            speaker_wav=speaker_wav_path,
            language=xtts_lang,
        )
        sf.write(output_path, result["wav"], 24000)  # XTTS-v2's native output rate

        duration = 0
        try:
            duration = librosa.get_duration(filename=output_path)
        except Exception:
            pass

        return {
            "success": True, "audio_path": output_path,
            "audio_url": f"/tts/audio/{filename}", "duration": duration,
            "filename": filename, "engine": "xtts_v2", "voice_cloned": True
        }
    except Exception as e:
        print(f"⚠️ XTTS synthesis failed, will fall back: {e}")
        return {"success": False, "error": str(e)}


def synthesize_with_pronunciation(text: str, language: str = 'rw') -> dict:
    """Per-word pronunciation stitching — kept as a secondary path for words
    with a learned pronunciation clip. For anything longer than a few words,
    prefer synthesize_with_voice (XTTS) which sounds far less robotic."""
    words = text.split()
    has_pronunciations = any(
        w.strip('.,!?;:').lower() in pronunciation_learner.pronunciation_db for w in words
    )

    if has_pronunciations and SF_AVAILABLE:
        audio_chunks = []
        try:
            for word in words:
                clean_word = word.strip('.,!?;:').lower()
                if clean_word in pronunciation_learner.pronunciation_db:
                    pron = pronunciation_learner.pronunciation_db[clean_word][-1]
                    audio_path = pron["audio_path"]
                    if os.path.exists(audio_path):
                        audio, _ = librosa.load(audio_path, sr=16000, mono=True)
                        audio_chunks.append(audio)
                        continue
                fallback = synthesize_with_gtts(word, language)
                if fallback.get("success"):
                    audio, _ = librosa.load(fallback["audio_path"], sr=16000, mono=True)
                    audio_chunks.append(audio)

            if audio_chunks:
                combined = np.concatenate(audio_chunks)
                output_path = os.path.join(TTS_OUTPUT_DIR, f"tts_{uuid.uuid4()}.wav")
                sf.write(output_path, combined, 16000)
                return {
                    "success": True, "audio_path": output_path,
                    "audio_url": f"/tts/audio/{os.path.basename(output_path)}",
                    "duration": len(combined) / 16000, "pronunciation_used": True,
                    "engine": "pronunciation_stitch"
                }
        except Exception as e:
            print(f"Pronunciation synthesis error: {e}")

    return synthesize_with_gtts(text, language)


def synthesize_with_voice(text: str, language: str, voice_id: Optional[int] = None) -> dict:
    """
    NEW: Main synthesis entry point used by /tts/synthesize.
    Priority:
      1. If voice_id given and XTTS is available -> voice-cloned synthesis
      2. If learned per-word pronunciations exist -> stitched pronunciation
      3. Otherwise -> gTTS
    """
    if voice_id and XTTS_AVAILABLE:
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT sample_audio_path FROM voice_models WHERE id = %s AND is_active = TRUE", (voice_id,))
        voice = cursor.fetchone()
        cursor.close()
        conn.close()

        if voice and voice.get("sample_audio_path"):
            result = synthesize_with_xtts(text, language, voice["sample_audio_path"])
            if result.get("success"):
                return result
            # fall through to other engines if XTTS failed at runtime

    return synthesize_with_pronunciation(text, language)


# ============================================
# DOCUMENT PROCESSOR INSTANCE
# ============================================

document_processor = DocumentProcessor()

# ============================================
# TTS ENDPOINTS
# ============================================

@app.post("/tts/upload-document")
async def tts_upload_document(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    print(f"\n📄 Uploading document: {file.filename}")

    ext = file.filename.split('.')[-1].lower()
    file_type_map = {
        'pdf': 'pdf', 'docx': 'docx', 'doc': 'docx',
        'txt': 'txt', 'text': 'txt',
        'jpg': 'jpg', 'jpeg': 'jpeg', 'png': 'png',
        'bmp': 'bmp', 'tiff': 'tiff'
    }
    file_type = file_type_map.get(ext, 'unknown')
    if file_type == 'unknown':
        raise HTTPException(400, f"Unsupported file type: {ext}")

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.{ext}"
    file_path = os.path.join(TTS_DOCS_DIR, safe_filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    result = document_processor.extract_text(file_path, file_type)

    conn = db.get_connection()
    cursor = conn.cursor()

    if result.get("success"):
        extracted_text = result.get("text", "")
        word_count = len(extracted_text.split()) if extracted_text else 0
        paragraph_count = len(extracted_text.split('\n\n')) if extracted_text else 0
        print(f"📊 Extracted {word_count} words, {paragraph_count} paragraphs")

        cursor.execute("""
            INSERT INTO tts_documents
            (user_id, filename, file_path, file_type, extracted_text, status, word_count, paragraph_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_user["id"], file.filename, file_path, file_type, extracted_text,
              'completed' if extracted_text else 'failed', word_count, paragraph_count))
        conn.commit()
        document_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return {
            "success": True, "document_id": document_id, "filename": file.filename,
            "file_type": file_type,
            "text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            "extracted_text": extracted_text,
            "text_length": len(extracted_text), "pages": result.get("pages", 1),
            "word_count": word_count, "paragraph_count": paragraph_count,
            "message": "✅ Document uploaded and processed successfully!"
        }
    else:
        cursor.execute("""
            INSERT INTO tts_documents
            (user_id, filename, file_path, file_type, extracted_text, status, word_count, paragraph_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_user["id"], file.filename, file_path, file_type, "", 'failed', 0, 0))
        conn.commit()
        document_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return {
            "success": False, "document_id": document_id, "filename": file.filename,
            "file_type": file_type, "error": result.get("error", "Failed to extract text from document"),
            "message": "⚠️ Document uploaded but text extraction failed"
        }


@app.post("/tts/rewrite-text")
async def tts_rewrite_text(request: Request, current_user=Depends(get_current_user)):
    try:
        data = await request.json()
        text = data.get('text', '')
        language = data.get('language', 'rw')
    except Exception:
        return {"success": False, "error": "Invalid JSON body"}

    if not text or not text.strip():
        return {"success": False, "error": "No text provided"}

    # NEW: try real LLM rewrite first
    llm_result = llm_rewrite_text(text, language)
    if llm_result:
        rewritten = llm_result
        engine = "llm"
    else:
        corrector = english_corrector if language == 'en' else kinyarwanda_corrector
        rewritten = corrector.correct_text(text)
        engine = "rule_based"

    rewritten = re.sub(r'\s+', ' ', rewritten)
    rewritten = re.sub(r'\s+([.,!?;:])', r'\1', rewritten)

    paragraphs = [' '.join(p.split()) for p in rewritten.split('\n\n') if p.strip()]
    rewritten = '\n\n'.join(paragraphs) if paragraphs else rewritten

    return {
        "success": True, "original": text, "rewritten": rewritten,
        "word_count": len(rewritten.split()), "paragraph_count": max(len(paragraphs), 1),
        "engine": engine
    }


@app.post("/tts/synthesize")
async def tts_synthesize(request: Request, current_user=Depends(get_current_user)):
    try:
        data = await request.json()
        text = data.get('text', '')
        language = data.get('language', 'rw')
        document_id = data.get('document_id')
        voice_id = data.get('voice_id')  # NEW
        gender = data.get('gender')  # persona, only used when no voice_id
    except Exception:
        return {"success": False, "error": "Invalid JSON body"}

    if language not in {'en', 'rw'}:
        return {"success": False, "error": "Only English and Kinyarwanda are supported"}

    if text and text.strip():
        content_text = text.strip()
    elif document_id:
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tts_documents WHERE id = %s AND user_id = %s",
                       (document_id, current_user["id"]))
        document = cursor.fetchone()
        cursor.close()
        conn.close()

        if not document:
            return {"success": False, "error": "Document not found"}
        content_text = document.get('extracted_text', '')
        if not content_text or not content_text.strip():
            return {"success": False, "error": "No text found in document"}
    else:
        return {"success": False, "error": "No text provided"}

    if voice_id:
        # A specific cloned voice was requested — try that (XTTS) first.
        result = synthesize_with_voice(content_text, language, voice_id)
    else:
        # No cloned voice: honor the requested persona via Edge TTS, the only
        # bundled engine with real voice variety — gTTS has no voice/gender
        # selection capability at all, so it can never satisfy this request.
        edge_voice = pick_edge_voice(language, gender)
        result = await synthesize_with_edge_tts(content_text, language, edge_voice)

    if not result.get("success"):
        prior_error = result.get("error", "Unknown error")
        result = await synthesize_with_edge_tts(content_text, language)
        if not result.get("success"):
            result = synthesize_with_pronunciation(content_text, language)
        if not result.get("success"):
            result["error"] = f"Synthesis failed: {prior_error}. {result.get('error', '')}"

    if result.get("success"):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tts_jobs (user_id, document_id, voice_id, output_path, status, progress)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (current_user["id"], document_id or None, voice_id or None,
              result.get("audio_path"), 'completed', 100))
        conn.commit()
        job_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return {
            "success": True, "job_id": job_id, "audio_url": result.get("audio_url"),
            "duration": result.get("duration", 0),
            "pronunciation_used": result.get("pronunciation_used", False),
            "voice_cloned": result.get("voice_cloned", False),
            "engine": result.get("engine"), "filename": result.get("filename")
        }

    return {"success": False, "error": result.get("error", "Synthesis failed")}


class VoicePreviewRequest(BaseModel):
    language: str = 'rw'
    gender: str = 'female'


@app.post("/tts/preview-voice")
async def preview_voice(data: VoicePreviewRequest, current_user=Depends(get_current_user)):
    """Short canned-phrase synthesis so clicking a voice persona gives quick
    audible feedback, without needing the user's own text typed in yet."""
    language = data.language if data.language in {'en', 'rw'} else 'rw'
    sample_text = {
        'rw': "Muraho, amakuru? Iyi ni ijwi ryo kugerageza.",
        'en': "Hello, how are you? This is a preview of this voice.",
    }[language]

    edge_voice = pick_edge_voice(language, data.gender)
    result = await synthesize_with_edge_tts(sample_text, language, edge_voice)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Voice preview failed"))

    return {"success": True, "audio_url": result.get("audio_url"), "voice": edge_voice}


@app.post("/tts/learn-pronunciation")
async def learn_pronunciation(word: str = Form(...), audio: UploadFile = File(...), transcript: Optional[str] = Form(None),
                               current_user=Depends(get_current_user)):
    print(f"\n🎙️ Learning pronunciation for: {word}")

    file_id = str(uuid.uuid4())
    safe_filename = f"pronunciation_{file_id}.wav"
    file_path = os.path.join(TTS_PRONUNCIATIONS_DIR, safe_filename)

    content = await audio.read()
    with open(file_path, "wb") as f:
        f.write(content)

    if not transcript:
        try:
            audio_array, sr = librosa.load(file_path, sr=16000, mono=True)
            audio_array = audio_array.astype(np.float32)
            inputs = processor(audio_array, sampling_rate=16000, return_tensors="pt")
            input_features = inputs.input_features.to(DEVICE)
            with torch.no_grad():
                predicted_ids = kinyarwanda_model.generate(
                    input_features, max_new_tokens=100, temperature=0.2, repetition_penalty=1.15,
                )
            transcript = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
        except Exception:
            transcript = word

    result = pronunciation_learner.learn_pronunciation(word, file_path, transcript)

    return {
        "success": True, "word": word, "transcript": transcript,
        "audio_path": f"/tts/pronunciations/{safe_filename}",
        "pronunciations": result.get("pronunciations", 0),
        "message": f"✅ Learned pronunciation for '{word}'"
    }


@app.get("/tts/pronunciations/{filename}")
async def get_pronunciation_audio(filename: str):
    audio_path = os.path.join(TTS_PRONUNCIATIONS_DIR, filename)
    if not os.path.exists(audio_path):
        raise HTTPException(404, "Audio not found")
    return FileResponse(audio_path, media_type="audio/wav")


@app.get("/tts/pronunciation/{word}")
async def get_pronunciation(word: str):
    pronunciation = pronunciation_learner.get_pronunciation(word)
    if not pronunciation:
        return {"success": False, "error": f"No pronunciation found for '{word}'"}
    return {
        "success": True, "word": word, "pronunciation": pronunciation,
        "audio_url": f"/tts/pronunciations/{os.path.basename(pronunciation['audio_path'])}"
    }


@app.get("/tts/pronunciations")
async def get_all_pronunciations():
    return {"success": True, "total": len(pronunciation_learner.pronunciation_db),
            "words": list(pronunciation_learner.pronunciation_db.keys())}


@app.get("/tts/documents")
async def tts_get_documents(current_user=Depends(get_current_user)):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, filename, file_type, status, created_at,
               LENGTH(extracted_text) as text_length, word_count, paragraph_count
        FROM tts_documents WHERE user_id = %s ORDER BY created_at DESC
    """, (current_user["id"],))
    documents = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"success": True, "documents": documents}


@app.get("/tts/jobs")
async def tts_get_jobs(current_user=Depends(get_current_user)):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT j.*, d.filename as document_name
        FROM tts_jobs j LEFT JOIN tts_documents d ON j.document_id = d.id
        WHERE j.user_id = %s ORDER BY j.created_at DESC
    """, (current_user["id"],))
    jobs = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"success": True, "jobs": jobs}


@app.get("/tts/audio/{filename}")
async def tts_get_audio(filename: str):
    audio_path = os.path.join(TTS_OUTPUT_DIR, filename)
    if not os.path.exists(audio_path):
        raise HTTPException(404, "Audio not found")
    media_type = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
    return FileResponse(audio_path, media_type=media_type)


@app.delete("/tts/document/{document_id}")
async def tts_delete_document(document_id: int, current_user=Depends(get_current_user)):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM tts_documents WHERE id = %s AND user_id = %s",
                   (document_id, current_user["id"]))
    doc = cursor.fetchone()
    if not doc:
        cursor.close()
        conn.close()
        return {"success": False, "error": "Document not found"}
    if doc[0] and os.path.exists(doc[0]):
        os.remove(doc[0])
    cursor.execute("DELETE FROM tts_documents WHERE id = %s", (document_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"success": True}


@app.get("/tts/voices")
async def tts_get_voices(current_user=Depends(get_current_user)):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, description, language, gender, age_group, voice_type, category, is_active
        FROM voice_models WHERE is_active = TRUE ORDER BY language, gender, age_group
    """)
    voices = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"success": True, "voices": voices, "voice_cloning_available": XTTS_AVAILABLE}


@app.post("/tts/register-voice")
async def tts_register_voice(name: str = Form(...), audio: UploadFile = File(...), language: str = Form("rw"),
                              gender: str = Form("female"), age_group: str = Form("adult"),
                              description: Optional[str] = Form(None), current_user=Depends(get_current_user)):
    print(f"\n🎙️ Registering voice: {name}")
    print(f"   Gender: {gender}, Age: {age_group}, Language: {language}")

    valid_genders = ['male', 'female', 'child', 'elderly_male', 'elderly_female',
                      'teenage_male', 'teenage_female', 'celebrity']
    valid_age_groups = ['child', 'teen', 'adult', 'elderly']

    if gender not in valid_genders:
        return {"success": False, "error": f"Invalid gender. Must be one of: {', '.join(valid_genders)}"}
    if age_group not in valid_age_groups:
        return {"success": False, "error": f"Invalid age group. Must be one of: {', '.join(valid_age_groups)}"}

    file_id = str(uuid.uuid4())
    safe_filename = f"voice_{file_id}.wav"
    file_path = os.path.join(TTS_VOICES_DIR, safe_filename)

    content = await audio.read()
    with open(file_path, "wb") as f:
        f.write(content)

    duration = 0
    try:
        duration = librosa.get_duration(filename=file_path)
    except Exception:
        pass

    # NEW: warn if the sample is too short for good XTTS cloning quality
    quality_warning = None
    if XTTS_AVAILABLE and duration < 6:
        quality_warning = ("Sample is shorter than 6 seconds — voice cloning quality will be "
                            "reduced. 10-20 seconds of clean, single-speaker audio is recommended.")

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO voice_models
            (user_id, name, description, language, gender, age_group, voice_type,
             category, sample_audio_path, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_user["id"], name, description or f"Custom voice: {name}", language, gender,
              age_group, 'custom', 'custom', file_path, True))
        conn.commit()
        voice_id = cursor.lastrowid

        try:
            cursor.execute("""
                INSERT INTO voice_registrations (user_id, voice_id, audio_path, transcript, duration, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (current_user["id"], voice_id, file_path, f"Voice registration: {name}", duration, 'completed'))
            conn.commit()
        except Exception as e:
            print(f"Voice registration tracking error: {e}")

        cursor.close()
        conn.close()

        return {
            "success": True, "voice_id": voice_id, "name": name, "language": language,
            "gender": gender, "age_group": age_group, "duration": round(duration, 2),
            "voice_cloning_ready": XTTS_AVAILABLE,
            "quality_warning": quality_warning,
            "message": f"✅ Voice '{name}' registered successfully!" + (
                " You can now pass this voice_id to /tts/synthesize to use it." if XTTS_AVAILABLE else
                " Note: install the TTS package to enable voice cloning with this sample."
            )
        }
    except Exception as e:
        print(f"Voice registration error: {e}")
        cursor.close()
        conn.close()
        return {"success": False, "error": str(e)}


# ============================================
# AUTH ENDPOINTS
# ============================================

@app.post("/api/auth/login")
async def login(data: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else None
    user = authenticate_user(data.username, data.password, client_ip)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token({"sub": str(user["id"])})
    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": user,
        "message": f"Welcome back, {user['username']}!"
    }


@app.post("/api/auth/register")
async def register(data: RegisterRequest):
    try:
        user = register_user(username=data.username, email=data.email, password=data.password,
                              full_name=data.full_name, role="user", created_by=None,
                              provider=data.provider or 'email')
        return {
            "success": True,
            "message": f"Account created for {user['username']}. Please keep your password safe.",
            "user": user,
            "email_sent": user.get('email_sent', False)
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/password/reset")
async def reset_password(data: PasswordResetRequest):
    try:
        result = reset_user_password(data.identifier, data.new_password)
        return {"success": True, "message": result["message"]}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/password/change")
async def change_password(data: PasswordChangeRequest, current_user=Depends(get_current_user)):
    try:
        result = change_user_password(current_user["id"], data.current_password, data.new_password)
        return {"success": True, "message": result["message"]}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/me")
async def me(current_user=Depends(get_current_user)):
    return {"success": True, "user": current_user}


@app.post("/api/auth/logout")
async def logout(response: Response):
    # Clear the httpOnly token cookie
    res = JSONResponse({"success": True, "message": "Logged out"})
    res.delete_cookie('token')
    return res


# ============================================
# OAuth: Google
# ============================================
@app.get("/api/auth/oauth/google")
async def oauth_google():
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT') or 'http://localhost:8000/api/auth/oauth/google/callback'
    if not client_id:
        raise HTTPException(status_code=500, detail="Google OAuth not configured (GOOGLE_CLIENT_ID missing)")
    scope = "openid email profile"
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
        f"&scope={scope}&access_type=offline&prompt=select_account"
    )
    return RedirectResponse(auth_url)


@app.get("/api/auth/oauth/google/callback")
async def oauth_google_callback(code: str | None = None):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code from Google")
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT') or 'http://localhost:8000/api/auth/oauth/google/callback'
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth not configured (client id/secret missing)")

    token_url = 'https://oauth2.googleapis.com/token'
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data={
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        })
        if token_resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Token exchange failed: {token_resp.text}")
        token_data = token_resp.json()
        access_token = token_data.get('access_token')

        userinfo_resp = await client.get('https://www.googleapis.com/oauth2/v2/userinfo', headers={
            'Authorization': f'Bearer {access_token}'
        })
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch user info: {userinfo_resp.text}")
        profile = userinfo_resp.json()

    email = profile.get('email')
    name = profile.get('name') or profile.get('given_name') or ''
    if not email:
        raise HTTPException(status_code=400, detail="Google account did not return an email address")

    # Check if user exists
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        # Create a new user with a random password
        import secrets
        base_username = (email.split('@')[0])[:40]
        username = base_username
        # Ensure username uniqueness
        conn = db.get_connection()
        cursor = conn.cursor()
        i = 1
        while True:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if not cursor.fetchone():
                break
            username = f"{base_username}{i}"
            i += 1
        cursor.close()
        conn.close()

        generated_password = secrets.token_urlsafe(16)
        new_user = register_user(username=username, email=email, password=generated_password, full_name=name, provider='google')
        user = {'id': new_user['id'], 'username': new_user['username'], 'email': new_user['email']}

    # Create JWT and set as httpOnly cookie, then redirect back to frontend
    token = create_access_token({"sub": str(user['id'])})
    frontend_redirect = os.getenv('FRONTEND_URL') or 'http://localhost:3000'
    response = RedirectResponse(frontend_redirect)
    cookie_secure = os.getenv('COOKIE_SECURE', 'False').lower() in ('1', 'true', 'yes')
    max_age = int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    response.set_cookie('token', token, httponly=True, secure=cookie_secure, samesite='lax', max_age=max_age)
    return response


# Temporary debug endpoints (remove in production)
@app.get("/debug/routes")
async def debug_routes():
    return {"routes": [r.path for r in app.routes]}


@app.get("/debug/cookies")
async def debug_cookies(request: Request):
    # Return cookies sent by the client for debugging only
    return {"cookies": dict(request.cookies)}


# ============================================
# ADMIN ENDPOINTS
# ============================================

@app.get("/api/admin/users")
async def get_all_users(current_user=Depends(require_permission("manage_users"))):
    users = db.get_all_users()
    return {"success": True, "users": users}


@app.post("/api/admin/users")
async def create_user(username: str, email: str, password: str, full_name: str = None,
                       role: str = "secretary", department: str = None, phone: str = None,
                       current_user=Depends(require_permission("manage_users"))):
    user = register_user(username=username, email=email, password=password, full_name=full_name,
                          role=role, department=department, phone=phone, created_by=current_user["id"])
    log_activity(current_user["id"], "CREATE_USER", f"Created user: {username}", None)
    return {"success": True, "user": user}


@app.put("/api/admin/users/{user_id}/status")
async def update_user_status(user_id: int, is_active: bool,
                              current_user=Depends(require_permission("manage_users"))):
    if user_id == current_user["id"]:
        raise HTTPException(400, "Cannot change your own status")
    updated = db.update_user_status(user_id, is_active)
    log_activity(current_user["id"], "UPDATE_USER_STATUS", f"User {user_id} status: {is_active}", None)
    return {"success": updated}


@app.get("/api/admin/stats")
async def get_system_stats(current_user=Depends(require_permission("view_stats"))):
    stats = db.get_system_stats()
    return {"success": True, "stats": stats}


# -------------------------
# User management (admin)
# -------------------------
class RoleChangeRequest(BaseModel):
    role: str


@app.post("/api/admin/users/{user_id}/role")
async def change_user_role(user_id: int, data: RoleChangeRequest, current_user=Depends(require_permission("manage_users"))):
    # Only admin/director can change roles
    new_role = (data.role or '').strip()
    if new_role == '':
        raise HTTPException(status_code=400, detail="Role is required")

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()

    log_activity(current_user["id"], "CHANGE_ROLE", f"Changed user {user_id} role to {new_role}", None)
    return {"success": True, "updated": affected > 0}


@app.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: int, current_user=Depends(require_permission("manage_users"))):
    # Admin-only
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    cursor.close()
    conn.close()

    if deleted:
        log_activity(current_user["id"], "DELETE_USER", f"Deleted user {user_id}", None)
    return {"success": deleted}


# -------------------------
# User profile endpoints
# -------------------------
class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None


@app.put("/api/user/profile")
async def update_profile(data: ProfileUpdateRequest, current_user=Depends(get_current_user)):
    # Ensure columns exist
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW COLUMNS FROM users LIKE 'full_name'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN full_name VARCHAR(255) NULL")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'department'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN department VARCHAR(255) NULL")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'phone'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(50) NULL")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'language_pref'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN language_pref VARCHAR(10) DEFAULT 'en'")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'avatar_url'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) NULL")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'bio'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT NULL")
    conn.commit()

    # Update fields
    updates = []
    params = []
    if data.full_name is not None:
        updates.append("full_name = %s")
        params.append(data.full_name)
    if data.department is not None:
        updates.append("department = %s")
        params.append(data.department)
    if data.phone is not None:
        updates.append("phone = %s")
        params.append(data.phone)
    if data.bio is not None:
        updates.append("bio = %s")
        params.append(data.bio)

    if updates:
        params.append(current_user['id'])
        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(sql, tuple(params))
        conn.commit()

    cursor.close()
    conn.close()

    log_activity(current_user['id'], 'UPDATE_PROFILE', 'Updated profile fields', None)
    return {"success": True}


@app.post("/api/user/profile/avatar")
async def upload_avatar(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    # Save avatar to uploads/avatars
    uploads_dir = os.path.join(os.getcwd(), 'uploads', 'avatars')
    os.makedirs(uploads_dir, exist_ok=True)
    filename = f"user_{current_user['id']}_{int(datetime.utcnow().timestamp())}_{file.filename}"
    file_path = os.path.join(uploads_dir, filename)

    with open(file_path, 'wb') as f:
        content = await file.read()
        f.write(content)

    # Store relative path in DB
    rel_path = f"/uploads/avatars/{filename}"
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW COLUMNS FROM users LIKE 'avatar_url'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) NULL")
        conn.commit()
    cursor.execute("UPDATE users SET avatar_url = %s WHERE id = %s", (rel_path, current_user['id']))
    conn.commit()
    cursor.close()
    conn.close()

    log_activity(current_user['id'], 'UPLOAD_AVATAR', f'Uploaded avatar: {rel_path}', None)
    return {"success": True, "avatar_url": rel_path}


class LanguageUpdateRequest(BaseModel):
    language: str


@app.post("/api/user/language")
async def set_language(data: LanguageUpdateRequest, current_user=Depends(get_current_user)):
    lang = (data.language or 'en').strip()[:10]
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW COLUMNS FROM users LIKE 'language_pref'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN language_pref VARCHAR(10) DEFAULT 'en'")
        conn.commit()
    cursor.execute("UPDATE users SET language_pref = %s WHERE id = %s", (lang, current_user['id']))
    conn.commit()
    cursor.close()
    conn.close()

    log_activity(current_user['id'], 'SET_LANGUAGE', f'Set language to {lang}', None)
    return {"success": True, "language": lang}


# -------------------------
# User settings (theme, font, default mode)
# -------------------------
class SettingsUpdateRequest(BaseModel):
    theme_color: Optional[str] = None
    font_style: Optional[str] = None
    default_mode: Optional[str] = None


def _ensure_settings_columns(cursor):
    cursor.execute("SHOW COLUMNS FROM users LIKE 'theme_color'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN theme_color VARCHAR(20) DEFAULT 'indigo'")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'font_style'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN font_style VARCHAR(20) DEFAULT 'inter'")
    cursor.execute("SHOW COLUMNS FROM users LIKE 'default_mode'")
    if cursor.fetchone() is None:
        cursor.execute("ALTER TABLE users ADD COLUMN default_mode VARCHAR(20) DEFAULT 'both'")


@app.get("/api/user/settings")
async def get_settings(current_user=Depends(get_current_user)):
    conn = db.get_connection()
    cursor = conn.cursor()
    _ensure_settings_columns(cursor)
    conn.commit()
    cursor.close()

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT theme_color, font_style, default_mode FROM users WHERE id = %s",
        (current_user['id'],)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return {"success": True, "settings": row or {}}


@app.put("/api/user/settings")
async def update_settings(data: SettingsUpdateRequest, current_user=Depends(get_current_user)):
    conn = db.get_connection()
    cursor = conn.cursor()
    _ensure_settings_columns(cursor)
    conn.commit()

    updates = []
    params = []
    if data.theme_color is not None:
        updates.append("theme_color = %s")
        params.append(data.theme_color.strip()[:20])
    if data.font_style is not None:
        updates.append("font_style = %s")
        params.append(data.font_style.strip()[:20])
    if data.default_mode is not None:
        updates.append("default_mode = %s")
        params.append(data.default_mode.strip()[:20])

    if updates:
        params.append(current_user['id'])
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = %s", tuple(params))
        conn.commit()

    cursor.close()
    conn.close()

    log_activity(current_user['id'], 'UPDATE_SETTINGS', 'Updated system settings', None)
    return {"success": True}


# -------------------------
# Support / contact
# -------------------------
class SupportContactRequest(BaseModel):
    message: str


@app.post("/api/support/contact")
async def contact_support(data: SupportContactRequest, current_user=Depends(get_current_user)):
    message = (data.message or '').strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    if len(message) > 5000:
        raise HTTPException(status_code=400, detail="Message is too long")

    sender_name = current_user.get('full_name') or current_user.get('username')
    sender_email = current_user.get('email') or ''
    body = (
        f"Support request from {sender_name} ({sender_email}), role: {current_user.get('role')}\n\n"
        f"{message}"
    )
    sent = send_email(
        'happyprincegodson@gmail.com',
        f"AudioText Pro Support Request from {current_user.get('username')}",
        body,
        reply_to=sender_email or None,
    )

    log_activity(current_user['id'], 'CONTACT_SUPPORT', 'Sent a support request', None)

    if not sent:
        raise HTTPException(status_code=502, detail="Unable to send your message right now. Please try WhatsApp instead.")
    return {"success": True}


# -------------------------
# Personal activity history (any authenticated user, own logs only)
# -------------------------
@app.get("/api/user/activity")
async def get_my_activity(limit: int = 50, current_user=Depends(get_current_user)):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, action, details, created_at FROM activity_logs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
        (current_user['id'], limit)
    )
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"success": True, "logs": logs}


# -------------------------
# Translation (English <-> Kinyarwanda)
# -------------------------
class TranslateRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str


@app.post("/api/translate")
async def translate_endpoint(data: TranslateRequest, current_user=Depends(get_current_user)):
    text = (data.text or '').strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    if len(text) > 20000:
        raise HTTPException(status_code=400, detail="Text is too long to translate at once")

    source_lang = (data.source_lang or '').strip().lower()
    target_lang = (data.target_lang or '').strip().lower()
    if source_lang not in NLLB_LANG_CODES or target_lang not in NLLB_LANG_CODES:
        raise HTTPException(status_code=400, detail="Only English (en) and Kinyarwanda (rw) are supported")

    if source_lang == target_lang:
        return {"success": True, "translated_text": text, "source_lang": source_lang, "target_lang": target_lang}

    try:
        translated = translate_text(text, source_lang, target_lang)
    except Exception as e:
        print(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail="Translation failed. Please try again.")

    log_activity(current_user['id'], 'TRANSLATE', f'{source_lang} -> {target_lang}', None)
    return {"success": True, "translated_text": translated, "source_lang": source_lang, "target_lang": target_lang}


# -------------------------
# Standalone text formatting / summary / key-points
# -------------------------
class TextAnalyzeRequest(BaseModel):
    text: str
    language: str = 'en'
    duration_seconds: Optional[float] = None


@app.post("/api/text/analyze")
async def analyze_text(data: TextAnalyzeRequest, current_user=Depends(get_current_user)):
    """Reformat into paragraphs and (re)generate summary/key points for
    arbitrary text — used to regenerate results after a transcript is edited,
    or for text that didn't go through the main transcribe pipeline."""
    text = (data.text or '').strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    language = data.language if data.language in {'en', 'rw'} else 'en'
    formatted_text = format_text_to_paragraphs(text, language)
    summary_result = generate_smart_summary(text, data.duration_seconds, language)
    key_points = extract_smart_key_points(text, data.duration_seconds)

    return {
        "success": True,
        "formatted_text": formatted_text,
        "summary": summary_result["summary"],
        "summary_metrics": {
            "type": summary_result["type"], "compression": summary_result["compression"],
            "original_words": summary_result["original_words"],
            "summary_words": summary_result["summary_words"],
        },
        "key_points": key_points,
    }


# -------------------------
# Record deletion (user or admin)
# -------------------------
@app.delete("/api/records/{record_id}")
async def delete_record(record_id: int, current_user=Depends(get_current_user)):
    # Allow users to delete their own records, admins/directors can delete any
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, file_path FROM audio_records WHERE id = %s", (record_id,))
    rec = cursor.fetchone()
    cursor.close()
    conn.close()

    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")

    owner_id = rec.get('user_id')
    if owner_id != current_user['id'] and current_user.get('role') not in ('director', 'admin', 'manager'):
        # check explicit permission
        if not has_permission(current_user, 'manage_records'):
            raise HTTPException(status_code=403, detail="Not allowed to delete this record")

    # Delete file from disk if exists
    try:
        file_path = rec.get('file_path')
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass

    deleted = db.delete_record(record_id, None if current_user.get('role') in ('director','admin') else current_user['id'])
    if deleted:
        log_activity(current_user['id'], 'DELETE_RECORD', f'Deleted record {record_id}', None)
    return {"success": deleted}


@app.get("/api/admin/activity")
async def get_activity_logs(limit: int = 100, current_user=Depends(require_permission("view_stats"))):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.*, u.username, u.full_name FROM activity_logs a
        LEFT JOIN users u ON a.user_id = u.id ORDER BY a.created_at DESC LIMIT %s
    """, (limit,))
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"success": True, "logs": logs}


# ============================================
# MAIN TRANSCRIBE ENDPOINT
# ============================================

@app.post("/upload")
async def upload_audio(file: UploadFile = File(...), language: str = Form("rw"),
                        current_user=Depends(get_current_user)):
    print(f"\n📥 File: {file.filename}")
    print(f"🌍 Selected language: {language}")
    print(f"👤 User: {current_user['username']}")

    if language not in ['en', 'rw']:
        return {"success": False, "error": "Invalid language. Please select English or Kinyarwanda"}

    file_id = str(uuid.uuid4())
    ext = file.filename.split('.')[-1]
    temp_path = os.path.join(Config.TEMP_DIR, f"{file_id}.{ext}")

    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    print(f"📊 File size: {file_size_mb:.2f} MB")

    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        result = transcribe_audio(temp_path, language)
        transcribed_text = result.get("text", "")
        duration_seconds = result.get("duration_seconds", 0)
        chunks_processed = result.get("chunks_processed", 0)

        if not transcribed_text or len(transcribed_text) < 10:
            return {"success": False, "error": "No clear speech detected. Please ensure good audio quality."}

        print(f"✅ Complete! Audio: {duration_seconds:.1f}s")
        print(f"📝 Text: {len(transcribed_text)} chars, {get_word_count(transcribed_text)} words")

        # transcribe_audio already inserted real paragraph breaks from pauses
        formatted_text = format_text_to_paragraphs(transcribed_text, language)
        summary_result = generate_smart_summary(transcribed_text, duration_seconds, language)
        key_points = extract_smart_key_points(transcribed_text, duration_seconds)
        word_count = get_word_count(transcribed_text)

        if duration_seconds < 60:
            duration_display = f"{int(duration_seconds)} seconds"
        elif duration_seconds < 3600:
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            duration_display = f"{minutes}m {seconds}s"
        else:
            hours = int(duration_seconds // 3600)
            minutes = int((duration_seconds % 3600) // 60)
            duration_display = f"{hours}h {minutes}m"

        audio_path = os.path.join(AUDIO_DIR, f"{file_id}.{ext}")
        with open(audio_path, "wb") as f:
            f.write(content)

        record_id = db.insert_record(
            filename=file.filename, file_path=audio_path, language=language,
            text=formatted_text, summary=summary_result["summary"], key_points=key_points,
            user_id=current_user["id"]
        )

        log_activity(current_user["id"], "TRANSCRIBE", f"Transcribed: {file.filename} ({language})", None)

        return {
            "success": True, "record_id": record_id, "language": language,
            "language_display": "English" if language == "en" else "Kinyarwanda",
            "text": formatted_text, "audio_url": f"/audio/{file_id}.{ext}",
            "text_metrics": {
                "word_count": word_count, "duration": duration_display,
                "duration_seconds": round(duration_seconds, 1),
                "sentence_count": len(re.findall(r'[.!?]+', transcribed_text)),
                "chunks_processed": chunks_processed,
                "paragraph_breaks_detected": result.get("paragraph_breaks_detected", 0),
                "file_size_mb": round(file_size_mb, 2)
            },
            "summary": summary_result["summary"],
            "summary_metrics": {
                "type": summary_result["type"], "compression": summary_result["compression"],
                "original_words": summary_result["original_words"],
                "summary_words": summary_result["summary_words"],
                "target_percent": summary_result["target_percent"]
            },
            "key_points": key_points
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ============================================
# SPEECH RECOGNITION ENDPOINTS
# ============================================

@app.post("/api/speech/save")
async def save_speech_recording(request: Request, current_user=Depends(get_current_user)):
    try:
        data = await request.json()
        text = data.get("text", "").strip()
        language = data.get("language", "rw")
        audio_base64 = data.get("audio", "")
        duration = data.get("duration", 0)
        word_count = data.get("word_count", 0)
        summary = data.get("summary", "")
        key_points = data.get("key_points", [])

        if not text:
            return {"success": False, "error": "No text provided"}

        corrector = english_corrector if language == 'en' else kinyarwanda_corrector
        text = corrector.correct_text(text)
        text = format_text_to_paragraphs(text, language)

        if not summary and text:
            summary = generate_smart_summary(text, duration, language)["summary"]
        if not key_points and text:
            key_points = extract_smart_key_points(text, duration)

        file_id = str(uuid.uuid4())
        audio_path = None

        if audio_base64 and len(audio_base64) > 100:
            try:
                if ',' in audio_base64:
                    audio_base64 = audio_base64.split(',')[1]
                audio_data = base64.b64decode(audio_base64)
                audio_path = os.path.join(AUDIO_DIR, f"speech_{file_id}.wav")
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
            except Exception as e:
                print(f"Audio save error: {e}")

        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO speech_recordings
            (user_id, language, text, summary, key_points, duration, word_count, audio_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_user["id"], language, text, summary, json.dumps(key_points),
              duration, word_count, audio_path))
        conn.commit()
        record_id = cursor.lastrowid
        cursor.close()
        conn.close()

        log_activity(current_user["id"], "SAVE_SPEECH", f"Saved speech recording: {record_id} ({language})", None)

        return {
            "success": True, "record_id": record_id, "text": text, "summary": summary,
            "key_points": key_points, "duration": duration, "word_count": word_count,
            "audio_url": f"/audio/{os.path.basename(audio_path)}" if audio_path else None
        }

    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/speech/records")
async def get_speech_records(current_user=Depends(get_current_user)):
    try:
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)

        is_director = current_user['role'] in ['director', 'admin']
        if is_director:
            cursor.execute("SELECT * FROM speech_recordings ORDER BY created_at DESC")
        else:
            cursor.execute("SELECT * FROM speech_recordings WHERE user_id = %s ORDER BY created_at DESC",
                            (current_user["id"],))
        records = cursor.fetchall()

        for record in records:
            if record.get('key_points'):
                try:
                    record['key_points'] = json.loads(record['key_points'])
                except Exception:
                    record['key_points'] = []
            if record.get('audio_path'):
                record['audio_url'] = f"/audio/{os.path.basename(record['audio_path'])}"

        cursor.close()
        conn.close()
        return {"success": True, "records": records}

    except Exception as e:
        print(f"Error: {e}")
        return {"success": True, "records": []}


@app.delete("/api/speech/record/{record_id}")
async def delete_speech_record(record_id: int, current_user=Depends(get_current_user)):
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, audio_path FROM speech_recordings WHERE id = %s", (record_id,))
        record = cursor.fetchone()

        if not record:
            cursor.close()
            conn.close()
            return {"success": False, "error": "Record not found"}

        is_director = current_user['role'] in ['director', 'admin']
        if not is_director and record[0] != current_user["id"]:
            cursor.close()
            conn.close()
            return {"success": False, "error": "Permission denied"}

        if record[1] and os.path.exists(record[1]):
            os.remove(record[1])

        cursor.execute("DELETE FROM speech_recordings WHERE id = %s", (record_id,))
        conn.commit()
        cursor.close()
        conn.close()

        log_activity(current_user["id"], "DELETE_SPEECH", f"Deleted speech record {record_id}", None)
        return {"success": True}

    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


# ============================================
# RECORDS MANAGEMENT
# ============================================

@app.get("/records")
async def get_records(current_user=Depends(get_current_user)):
    include_all = current_user['role'] == 'director'
    records = db.get_all_records(user_id=current_user["id"], include_all=include_all)
    for r in records:
        if r.get('file_path') and os.path.exists(r['file_path']):
            r['audio_url'] = f"/audio/{os.path.basename(r['file_path'])}"
    return {"success": True, "records": records, "user_role": current_user['role']}


@app.delete("/record/{record_id}")
async def delete_record(record_id: int, current_user=Depends(get_current_user)):
    if current_user['role'] == 'director':
        deleted = db.delete_record(record_id, user_id=None)
    else:
        deleted = db.delete_record(record_id, user_id=current_user["id"])
    if deleted:
        log_activity(current_user["id"], "DELETE_RECORD", f"Deleted record {record_id}", None)
    return {"success": deleted}


@app.post("/save-kinyarwanda")
async def save_kinyarwanda(request: Request, current_user=Depends(get_current_user)):
    try:
        data = await request.json()
        text = data.get("text", "")
        audio_base64 = data.get("audio", "")

        if not text:
            return {"success": False, "error": "No text provided"}

        text = kinyarwanda_corrector.correct_text(text)
        formatted_text = format_text_to_paragraphs(text, 'rw')

        file_id = str(uuid.uuid4())
        audio_path = None

        if audio_base64 and len(audio_base64) > 100:
            try:
                if ',' in audio_base64:
                    audio_base64 = audio_base64.split(',')[1]
                audio_data = base64.b64decode(audio_base64)
                audio_path = os.path.join(AUDIO_DIR, f"kinyarwanda_{file_id}.wav")
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
            except Exception as e:
                print(f"Audio error: {e}")

        word_count = get_word_count(text)
        duration = f"{int(word_count / 150)} minutes" if word_count > 150 else f"{int(word_count / 150 * 60)} seconds"
        summary_result = generate_smart_summary(text, language='rw')
        key_points = extract_smart_key_points(text)

        record_id = db.insert_record(
            filename=f"kinyarwanda_recording_{file_id}.wav",
            file_path=audio_path if audio_path else "", language="rw",
            text=formatted_text, summary=summary_result["summary"], key_points=key_points,
            user_id=current_user["id"]
        )

        log_activity(current_user["id"], "SAVE_KINYARWANDA", f"Saved recording: {record_id}", None)

        return {
            "success": True, "record_id": record_id, "text": formatted_text,
            "summary": summary_result["summary"], "key_points": key_points,
            "summary_metrics": {
                "compression": summary_result["compression"],
                "original_words": summary_result["original_words"],
                "summary_words": summary_result["summary_words"]
            },
            "audio_url": f"/audio/kinyarwanda_{file_id}.wav" if audio_path else None,
            "text_metrics": {"word_count": word_count, "duration": duration}
        }

    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


# ============================================
# AUDIO AND EXPORT ENDPOINTS
# ============================================

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    audio_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(audio_path):
        raise HTTPException(404, "Audio not found")
    return FileResponse(audio_path, media_type="audio/mpeg")


@app.get("/export/txt/{record_id}")
async def export_txt(record_id: int, current_user=Depends(get_current_user)):
    if current_user['role'] != 'director':
        record = db.get_record_by_id(record_id, current_user["id"])
    else:
        record = db.get_record_by_id(record_id)

    if not record:
        raise HTTPException(404, "Record not found")

    content = f"""
{'='*60}
AUDIO TRANSCRIPTION REPORT
{'='*60}

Filename: {record.get('filename', 'Unknown')}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Language: {'Kinyarwanda' if record.get('language_detected') == 'rw' else 'English'}
User: {current_user['username']}

{'='*60}
FULL TRANSCRIPTION
{'='*60}

{record.get('original_text', '')}

{'='*60}
AI SUMMARY
{'='*60}

{record.get('summary_text', '')}

{'='*60}
KEY POINTS
{'='*60}

"""
    key_points = record.get('key_points', [])
    if isinstance(key_points, str):
        try:
            key_points = json.loads(key_points)
        except Exception:
            key_points = [key_points]

    for i, point in enumerate(key_points, 1):
        text = point.get('text', point) if isinstance(point, dict) else point
        content += f"{i}. {text}\n\n"

    content += f"\n{'='*60}\nEnd of Report\n{'='*60}"

    return Response(content=content, media_type="text/plain",
                     headers={"Content-Disposition": f"attachment; filename=transcription_{record_id}.txt"})


@app.get("/export/pdf/{record_id}")
async def export_pdf(record_id: int, current_user=Depends(get_current_user)):
    if not PDF_AVAILABLE:
        raise HTTPException(501, "PDF export not available")

    if current_user['role'] != 'director':
        record = db.get_record_by_id(record_id, current_user["id"])
    else:
        record = db.get_record_by_id(record_id)

    if not record:
        raise HTTPException(404, "Record not found")

    pdf_path = os.path.join(Config.TEMP_DIR, f"report_{record_id}.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24,
                                  textColor=colors.HexColor('#0284c7'), spaceAfter=30, alignment=TA_CENTER)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=16,
                                    textColor=colors.HexColor('#1e3a5f'), spaceAfter=12, spaceBefore=20)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=11,
                                 leading=14, alignment=TA_JUSTIFY, spaceAfter=12)

    story = [
        Paragraph("Audio Transcription Report", title_style),
        Spacer(1, 0.2 * inch),
        Paragraph(f"<b>Filename:</b> {record.get('filename', 'Unknown')}", body_style),
        Paragraph(f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style),
        Paragraph(f"<b>Language:</b> {'Kinyarwanda' if record.get('language_detected') == 'rw' else 'English'}", body_style),
        Spacer(1, 0.3 * inch),
        Paragraph("📝 Full Transcription", heading_style),
        Paragraph(record.get('original_text', '').replace('\n', '<br/>'), body_style),
        Spacer(1, 0.2 * inch),
        Paragraph("📋 AI Summary", heading_style),
        Paragraph(record.get('summary_text', '').replace('\n', '<br/>'), body_style),
        Spacer(1, 0.2 * inch),
        Paragraph("🔑 Key Points", heading_style),
    ]

    key_points = record.get('key_points', [])
    if isinstance(key_points, str):
        try:
            key_points = json.loads(key_points)
        except Exception:
            key_points = [key_points]

    for i, point in enumerate(key_points, 1):
        text = point.get('text', point) if isinstance(point, dict) else point
        story.append(Paragraph(f"{i}. {text}", body_style))

    doc.build(story)
    log_activity(current_user["id"], "EXPORT_PDF", f"Exported record {record_id}", None)
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"transcription_{record_id}.pdf")


@app.get("/")
async def root():
    return {
        "message": "EVA API - Enhanced Version",
        "version": "11.0.0",
        "features": {
            "audio_preprocessing": True,
            "english_model": "openai/whisper-small",
            "kinyarwanda_model": "pacomesimon/whisper-small-rw",
            "pause_based_paragraphing": True,
            "english_correction_engine": "languagetool" if LANGUAGETOOL_AVAILABLE else "rule_based_fallback",
            "kinyarwanda_correction_engine": "wordlist_spellcheck" if kinyarwanda_corrector.vocab else "punctuation_only",
            "llm_rewrite_and_summary": LLM_REWRITE_ENABLED,
            "unlimited_audio": True,
            "ocr_support": OCR_AVAILABLE,
            "document_support": PDF_AVAILABLE_TTS or DOCX_AVAILABLE,
            "pronunciation_learning": True,
            "voice_cloning_tts": XTTS_AVAILABLE,
            "gtts_fallback": GTTS_AVAILABLE
        },
        "status": "active"
    }


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("🎙️ EVA - ENHANCED VERSION")
    print("=" * 60)
    print("✅ Server: http://localhost:8000")
    print("✅ English Model: openai/whisper-small")
    print(f"✅ Kinyarwanda Model: {KINYARWANDA_MODEL_ID}")
    print(f"✅ Device: {DEVICE.upper()}")
    print(f"✅ Pause-based paragraphing: Enabled")
    print(f"✅ English correction: {'LanguageTool' if LANGUAGETOOL_AVAILABLE else 'Rule-based fallback only'}")
    print(f"✅ Kinyarwanda spellcheck: {'Wordlist loaded' if kinyarwanda_corrector.vocab else 'Not configured (see rw_wordlist.txt)'}")
    print(f"✅ LLM rewrite/summary: {'Enabled' if LLM_REWRITE_ENABLED else 'Disabled (set ANTHROPIC_API_KEY)'}")
    print(f"✅ Voice cloning (XTTS-v2): {'Available' if XTTS_AVAILABLE else 'Not installed'}")
    print(f"✅ gTTS Fallback: {'Available' if GTTS_AVAILABLE else 'Not available'}")
    print("=" * 60 + "\n")

    try:
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except TypeError:
        uvicorn.run(app, host="127.0.0.1", port=8000, loop="asyncio")
