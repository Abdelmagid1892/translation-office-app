import html
import re
from pathlib import Path
from typing import Tuple

from docx import Document
from pdfminer.high_level import extract_text as pdf_extract_text


def extract_text_from_file(path: Path) -> Tuple[str, str]:
    """Return extracted text and detected extension."""
    suffix = path.suffix.lower()
    text = ""
    if suffix == ".pdf":
        text = pdf_extract_text(str(path)) or ""
    elif suffix == ".docx":
        document = Document(str(path))
        paragraphs = [p.text for p in document.paragraphs]
        text = "\n".join(paragraphs)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
    return text, suffix


def count_words(text: str) -> int:
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def sanitize_message(text: str) -> str:
    safe_text = text.strip()[:1000]
    return html.escape(safe_text).replace("\n", "<br>")


def compare_numbers(source: str, target: str) -> bool:
    pattern = re.compile(r"\d+(?:[\.,]\d+)?")
    source_numbers = sorted(pattern.findall(source))
    target_numbers = sorted(pattern.findall(target))
    return source_numbers == target_numbers
