"""Best-effort plain-text extraction from stored resume files.

Resumes are stored exactly as the applicant uploaded them (PDF/DOC/DOCX/TXT)
and the project deliberately carries no third-party document parser, so
extraction here is dependency-free:

* ``.txt``  — decoded directly (UTF-8 with a Windows-1252 fallback).
* ``.docx`` — a ZIP archive; paragraph text is read from ``word/document.xml``
  with the standard library only.
* ``.pdf``  — text is pulled out of the page content streams (FlateDecode via
  ``zlib`` plus the text-showing operators ``Tj``/``TJ``). Scanned or
  image-only PDFs carry no text layer and therefore yield no text.
* ``.doc``  — the legacy binary Word format cannot be parsed without a real
  parser; callers get a clear reason and continue without resume text.

Extraction never raises for a missing/corrupt/unsupported file: it returns a
:class:`ResumeText` describing what happened, so an analysis can still run on
the job requirements + application-form answers and the UI can tell HR that the
uploaded resume could not be read.
"""

import re
import zlib
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

#: Hard cap on decoded text (the AI prompt is capped separately).
MAX_EXTRACTED_CHARS = 200_000


@dataclass(frozen=True)
class ResumeText:
    """Result of a resume extraction attempt."""

    text: str = ""
    #: Human-readable reason why no text is available (never a stack trace).
    unavailable_reason: str | None = None
    #: True when the extracted text was cut at the length limit.
    truncated: bool = False

    @property
    def available(self) -> bool:
        """True when usable resume text was extracted."""
        return bool(self.text.strip())


def _resolve_path(relative_path: str) -> Path | None:
    """Map a stored ``resumes/<file>`` reference to a path inside UPLOAD_DIR.

    Returns ``None`` for empty references or any path that would escape the
    uploads directory (defence in depth: values come from our own database).
    """
    if not relative_path:
        return None
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    uploads_root = Path(settings.UPLOAD_DIR).resolve()
    resolved = (uploads_root / candidate).resolve()
    if uploads_root not in resolved.parents:
        return None
    return resolved


def _decode_text_file(content: bytes) -> str:
    """Decode a plain-text resume, falling back to single-byte encodings."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _unescape_pdf_string(value: bytes) -> str:
    """Decode a PDF string literal (handles escapes and UTF-16BE)."""
    out = bytearray()
    index = 0
    while index < len(value):
        byte = value[index]
        if byte == 0x5C and index + 1 < len(value):  # backslash escape
            nxt = value[index + 1]
            mapping = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
            if nxt in mapping:
                out.append(mapping[nxt])
                index += 2
                continue
            if 0x30 <= nxt <= 0x37:  # octal escape (\ddd)
                digits = ""
                index += 1
                while (
                    index < len(value)
                    and len(digits) < 3
                    and 0x30 <= value[index] <= 0x37
                ):
                    digits += chr(value[index])
                    index += 1
                out.append(int(digits, 8) & 0xFF)
                continue
            out.append(nxt)
            index += 2
            continue
        out.append(byte)
        index += 1

    raw = bytes(out)
    if raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            pass
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _decode_hex_string(hex_digits: bytes) -> str:
    """Decode a PDF hex string (``<48656C6C6F>``)."""
    cleaned = re.sub(rb"\s+", b"", hex_digits)
    if len(cleaned) % 2:
        cleaned += b"0"
    try:
        raw = bytes.fromhex(cleaned.decode("ascii"))
    except (ValueError, UnicodeDecodeError):
        return ""
_PDF_STRING_RE = re.compile(rb"\((?:\\.|[^\\()])*\)", re.DOTALL)
_PDF_HEX_RE = re.compile(rb"<([0-9A-Fa-f\s]{2,})>")
_PDF_TJ_ARRAY_RE = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)
_PDF_TJ_SINGLE_RE = re.compile(
    rb"(\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>)\s*(?:Tj|'|\")", re.DOTALL
)


def _extract_pdf_stream_text(stream: bytes) -> str:
    """Pull the text-showing operands out of one decompressed PDF stream."""
    pieces: list[str] = []
    for array_match in _PDF_TJ_ARRAY_RE.finditer(stream):
        operand = array_match.group(1)
        for literal in _PDF_STRING_RE.finditer(operand):
            pieces.append(_unescape_pdf_string(literal.group(0)[1:-1]))
        for hex_string in _PDF_HEX_RE.finditer(operand):
            pieces.append(_decode_hex_string(hex_string.group(1)))
    for single in _PDF_TJ_SINGLE_RE.finditer(stream):
        operand = single.group(1)
        if operand.startswith(b"("):
            pieces.append(_unescape_pdf_string(operand[1:-1]))
        else:
            pieces.append(_decode_hex_string(operand[1:-1]))
    return " ".join(piece for piece in pieces if piece.strip())


def _inflate(data: bytes) -> bytes | None:
    """FlateDecode a PDF stream, tolerating the syntax EOL after the data.

    The trailing ``\\n``/``\\r\\n`` that precedes ``endstream`` belongs to the PDF
    syntax, but compressed data may legitimately end with those bytes too, so
    every candidate is tried before giving up.
    """
    candidates = [data]
    stripped = data.rstrip(b"\r\n")
    if stripped != data:
        candidates.append(stripped)
    for candidate in candidates:
        try:
            return zlib.decompress(candidate)
        except zlib.error:
            continue
    # Truncated / unusual stream: decompress as much as available.
    try:
        partial = zlib.decompressobj().decompress(data)
    except zlib.error:
        return None
    return partial or None


def _extract_pdf_text(content: bytes) -> str:
    """Best-effort text extraction from a PDF file's content streams."""
    pages: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        data = match.group(1)
        # Content streams are usually FlateDecode-compressed; fall back to the
        # raw bytes for uncompressed streams (or a compression we cannot read).
        decoded = _inflate(data)
        if decoded is None:
            decoded = data.rstrip(b"\r\n")
        if b"Tj" not in decoded and b"TJ" not in decoded:
            continue
        text = _extract_pdf_stream_text(decoded)
        if text.strip():
            pages.append(text)
    return "\n".join(pages)


_DOCX_PARAGRAPH_RE = re.compile(rb"<w:p[ >].*?</w:p>", re.DOTALL)
_DOCX_TEXT_RE = re.compile(rb"<w:t[^>]*>(.*?)</w:t>", re.DOTALL)


def _extract_docx_text(content: bytes) -> str:
    """Extract paragraph text from a DOCX (OOXML) file."""
    import html
    import io
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            document = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""

    paragraphs: list[str] = []
    for paragraph in _DOCX_PARAGRAPH_RE.findall(document):
        chunk = b"".join(_DOCX_TEXT_RE.findall(paragraph))
        text = html.unescape(
            re.sub(rb"<[^>]+>", b" ", chunk).decode("utf-8", "replace")
        )
        text = " ".join(text.split())
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_resume_text(
    relative_path: str, *, max_chars: int = MAX_EXTRACTED_CHARS
) -> ResumeText:
    """Extract plain text from a stored resume file.

    Args:
        relative_path: Value stored in ``applications.resume_path`` (e.g.
            ``resumes/<hex>.pdf``).
        max_chars: Upper bound for the returned text.

    Returns:
        A :class:`ResumeText` with either the extracted text or a reason why no
        text is available. Never raises.
    """
    path = _resolve_path(relative_path)
    if path is None:
        return ResumeText(
            unavailable_reason="No resume file is attached to this application."
        )
    if not path.is_file():
        return ResumeText(
            unavailable_reason="The uploaded resume file could not be found."
        )

    suffix = path.suffix.lower()
    if suffix == ".doc":
        return ResumeText(
            unavailable_reason=(
                "Legacy .doc (Word 97-2003) files cannot be read automatically; "
                "the analysis used the application answers only."
            )
        )

    try:
        content = path.read_bytes()
    except OSError:
        return ResumeText(
            unavailable_reason="The uploaded resume file could not be read."
        )

    if suffix == ".txt":
        text = _decode_text_file(content)
    elif suffix == ".docx":
        text = _extract_docx_text(content)
    elif suffix == ".pdf":
        text = _extract_pdf_text(content)
    else:
        return ResumeText(
            unavailable_reason=(
                "Unsupported resume format; the analysis used the application "
                "answers only."
            )
        )

    text = " ".join(text.split())
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]

    if not text.strip():
        return ResumeText(
            unavailable_reason=(
                "No readable text was found in the uploaded resume (it may be a "
                "scanned/image-only file); the analysis used the application "
                "answers only."
            )
        )
    return ResumeText(text=text, truncated=truncated)
    if raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""
    return raw.decode("latin-1")