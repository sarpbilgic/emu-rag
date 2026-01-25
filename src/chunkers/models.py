"""
Data models for the structured HTML ingestion pipeline.
Defines block types and Article objects for regulation documents.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Literal, Union
from enum import Enum


class BlockType(str, Enum):
    """Types of structural blocks extracted from HTML."""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"


@dataclass
class HeadingBlock:
    """A heading element (h1-h6)."""
    type: Literal["heading"] = "heading"
    level: int = 2
    text: str = ""


@dataclass
class ParagraphBlock:
    """A paragraph element."""
    type: Literal["paragraph"] = "paragraph"
    text: str = ""


@dataclass
class TableBlock:
    """A table element with rows as list of lists."""
    type: Literal["table"] = "table"
    rows: List[List[str]] = field(default_factory=list)
    has_header: bool = False


@dataclass
class ListBlock:
    """A list element (ul/ol)."""
    type: Literal["list"] = "list"
    items: List[str] = field(default_factory=list)
    ordered: bool = False


# Union type for all block types
Block = Union[HeadingBlock, ParagraphBlock, TableBlock, ListBlock]


@dataclass
class StructuredDocument:
    """
    A document parsed from HTML with preserved structure.
    Output of Step 1 (scraping).
    """
    source: str
    document_title: Optional[str]
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Article:
    """
    A grouped article from a regulation document.
    Output of Step 3 (grouping).
    
    Rules:
    - Never merge articles
    - Never split at this stage
    - Tables stay inside their article
    """
    article_number: str
    article_title: Optional[str]
    blocks: List[Block]
    source: str
    document_title: Optional[str] = None
    section_title: Optional[str] = None  # e.g., "I. GENERAL PROVISIONS"


@dataclass
class Chunk:
    """
    A chunk ready for embedding.
    Output of Step 5 (splitting).
    
    Metadata preserved for retrieval/citation.
    """
    text: str
    article_number: str
    article_title: Optional[str]
    source: str
    document_title: Optional[str]
    section_title: Optional[str] = None  # e.g., "I. GENERAL PROVISIONS"
    chunk_index: int = 0
    total_chunks: int = 1
    contains_table: bool = False

