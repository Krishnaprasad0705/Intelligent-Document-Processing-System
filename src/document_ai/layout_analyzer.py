"""
Layout Analyzer.
Segments document text into lines, sections, and blocks, preserving
reading order and identifying visual delimiters.
"""

from dataclasses import dataclass
import re
from typing import List, Tuple
from document_ai.schemas import PageExtraction


@dataclass
class TextLine:
    line_number: int
    text: str
    page_number: int


def segment_into_lines(pages: List[PageExtraction]) -> List[TextLine]:
    """
    Breaks multi-page extraction text into sequenced lines
    retaining their original page number and line index.
    """
    lines: List[TextLine] = []
    line_counter = 1
    for page in pages:
        for raw_line in page.text.splitlines():
            stripped = raw_line.strip()
            if stripped:
                lines.append(
                    TextLine(
                        line_number=line_counter,
                        text=stripped,
                        page_number=page.page_number,
                    )
                )
                line_counter += 1
    return lines
