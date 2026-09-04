from __future__ import annotations

import asyncio
import io
import re
from dataclasses import dataclass

from app.core.errors import AppError

SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "image/png": "png", "image/jpeg": "jpg", "image/tiff": "tiff",
}


@dataclass
class ExtractedDocument:
    text: str
    page_count: int | None = None


@dataclass
class Chunk:
    index: int
    content: str
    page_number: int | None = None


class DocumentService:
    def validate(self, filename: str, content_type: str, content: bytes, max_bytes: int) -> str:
        if not content or len(content) > max_bytes:
            raise AppError("invalid_document_size", f"Document must be between 1 and {max_bytes} bytes", status_code=413)
        document_type = SUPPORTED_TYPES.get(content_type.split(";", 1)[0].lower())
        if not document_type:
            raise AppError("unsupported_document_type", "Only PDF, DOCX, TXT, PNG, JPEG, and TIFF are supported", status_code=415)
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed_extensions = {"jpg", "jpeg"} if document_type == "jpg" else {document_type}
        if extension not in allowed_extensions:
            raise AppError("document_type_mismatch", "Filename extension does not match the content type", status_code=415)
        signatures = {
            "pdf": content.startswith(b"%PDF-"), "docx": content.startswith(b"PK"),
            "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            "jpg": content.startswith(b"\xff\xd8\xff"),
            "tiff": content.startswith((b"II*\x00", b"MM\x00*")),
        }
        if document_type == "txt":
            try:
                content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise AppError("invalid_text_encoding", "Text documents must use UTF-8 encoding", status_code=415) from exc
        elif not signatures.get(document_type, False):
            raise AppError("invalid_document_signature", "File content does not match its declared type", status_code=415)
        return document_type

    async def extract(self, content: bytes, document_type: str) -> ExtractedDocument:
        return await asyncio.to_thread(self._extract_sync, content, document_type)

    def _extract_sync(self, content: bytes, document_type: str) -> ExtractedDocument:
        if document_type == "pdf":
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return ExtractedDocument("\n\n".join((page.extract_text() or "").strip() for page in reader.pages), len(reader.pages))
        if document_type == "docx":
            from docx import Document
            doc = Document(io.BytesIO(content))
            return ExtractedDocument("\n".join(p.text for p in doc.paragraphs if p.text.strip()))
        if document_type == "txt":
            return ExtractedDocument(content.decode("utf-8-sig"))
        from PIL import Image
        import pytesseract
        return ExtractedDocument(pytesseract.image_to_string(Image.open(io.BytesIO(content))))

    def clean(self, text: str) -> str:
        text = text.replace("\x00", "")
        return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()

    def chunk(self, text: str, target_chars: int = 1600, overlap_chars: int = 200) -> list[Chunk]:
        if not text:
            return []
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks, current = [], ""
        for paragraph in paragraphs:
            pieces = [paragraph[i:i + target_chars] for i in range(0, len(paragraph), target_chars)]
            for piece in pieces:
                if current and len(current) + len(piece) + 2 > target_chars:
                    chunks.append(Chunk(len(chunks), current))
                    current = current[-overlap_chars:] + "\n\n" + piece
                else:
                    current = f"{current}\n\n{piece}".strip()
        if current:
            chunks.append(Chunk(len(chunks), current))
        return chunks
