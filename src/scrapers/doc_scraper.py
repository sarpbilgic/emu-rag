"""
Structured HTML scraper for EMU regulations.
Implements Steps 1-2 of the pipeline:
  Step 1: Scrape HTML and keep structure (no Markdown yet)
  Step 2: Detect article boundaries

Includes normalization layer to recover structure from Word-exported HTML.

Output: StructuredDocument with preserved block types.
"""
import requests
import time
import re
import json
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag, NavigableString

from src.chunkers.models import (
    StructuredDocument,
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
    ListBlock,
    Block,
)


BASE_URL = "https://mevzuat.emu.edu.tr/"

# All regulation .htm files to scrape
HTM_LINKS = [
    "3-1_YabDilIngHzrOkul_en.htm",
    "5-1-0-Regulation-Education_Examination_Success.htm",
    "5-1-1-Rules-Entrance_exam.htm",
    "5-1-2-Rules-Scholarship_regulations.htm",
    "5-1-3-Rules-Vertical_transfer.htm",
    "5-1-4-Rules-examinations_and_evaluations.htm",
    "5-1-5-Rules-Course_Registration.htm",
    "5-1-6-Rules-Taking_courses_outside_the_university.htm",
    "5-1-7-Rules-Doublemajorprgs.htm",
    "5-1-8-Rules-Minorbylaw.htm",
    "5-1-9-Regulations%20for%20Summer%20Semester.htm",
    "5-1-10-Regulations-RegulationsforTutionFees.htm",
    "5-2-0-Rules-student_disciplinary.htm",
    "5-4-1-Rules-GraduateRegistrationandAdmissions.htm",
    "5-5-Disabled_Std_Principles.htm",
    "8_1_0_RegulationsPrinciplesStudentDormitories.htm",
    "REGULATIONS%20FOR%20BENEFITING%20FROM%20UNIVERSITY%20HOUSING%20AND%20GUEST%20HOUSE%20FACILITIES%20.htm",
]

# Step 2: Single regex for article boundary detection
ARTICLE_RE = re.compile(r"^(\d+[A-Za-z]?)\.?$")  # Matches "1." or "1" or "1a."

# Patterns for pseudo-headings (paragraphs that should be headings)
# Match both "I. GENERAL PROVISIONS" and "I. General Provisions"
ROMAN_NUMERAL_RE = re.compile(r"^[IVX]+\.\s+.+$", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^CHAPTER\s+[IVX\d]+", re.IGNORECASE)
PART_RE = re.compile(r"^PART\s+[IVX\d]+", re.IGNORECASE)
SECTION_RE = re.compile(r"^SECTION\s+[IVX\d]+", re.IGNORECASE)

# Disclaimer patterns to skip for title detection
DISCLAIMER_PATTERNS = [
    r"in the event of.*absence.*mutual agreement",
    r"turkish version.*regulations.*valid",
    r"english version.*these regulations",
]


class BlockNormalizer:
    """
    Normalizes raw blocks to recover structure from Word-exported HTML.
    
    Word HTML lies about structure:
    - Headings appear as <p><b>TEXT</b></p>
    - Articles are embedded in table rows
    - Tables are used for layout, not data
    
    This layer recovers intended structure using deterministic rules.
    """
    
    def _is_pseudo_heading(self, text: str) -> Tuple[bool, int]:
        """
        Detect if text should be a heading, not a paragraph.
        Returns (is_heading, level).
        """
        if not text or len(text) > 150:
            return False, 0
        
        text_stripped = text.strip()
        
        # Document titles - ALL CAPS, short, regulatory keywords
        if len(text_stripped) < 100:
            # Check if mostly uppercase
            alpha_chars = [c for c in text_stripped if c.isalpha()]
            if alpha_chars:
                uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                
                # ALL CAPS document titles
                if uppercase_ratio > 0.8:
                    # Known document title patterns
                    title_keywords = [
                        "REGULATION", "RULES", "PRINCIPLES", "BY-LAW", "BYLAW",
                        "STATUTE", "CODE", "PROVISIONS", "HOUSING", "DISCIPLINARY",
                        "DORMITOR", "EXAMINATION", "REGISTRATION", "SCHOLARSHIP"
                    ]
                    if any(kw in text_stripped.upper() for kw in title_keywords):
                        return True, 1
        
        # CHAPTER X, PART X, SECTION X
        if CHAPTER_RE.match(text_stripped):
            return True, 2
        if PART_RE.match(text_stripped):
            return True, 2
        if SECTION_RE.match(text_stripped):
            return True, 2
        
        # Roman numeral sections: "I. GENERAL PROVISIONS" or "I. General Provisions"
        if ROMAN_NUMERAL_RE.match(text_stripped):
            return True, 2
        
        # Standalone section headers (short, all caps)
        if len(text_stripped) < 60:
            alpha_chars = [c for c in text_stripped if c.isalpha()]
            if alpha_chars and len(alpha_chars) > 3:
                uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                if uppercase_ratio > 0.9:
                    # e.g., "AIM, SCOPE, DEFINITIONS AND GENERAL PROVISIONS"
                    return True, 2
        
        # Mixed case section titles: "General Provisions", "Main Provisions", "Final Provisions"
        provision_keywords = ["provisions", "concluding", "miscellaneous", "temporary"]
        if len(text_stripped) < 50 and any(kw in text_stripped.lower() for kw in provision_keywords):
            return True, 2
        
        return False, 0
    
    def _is_article_row(self, row: List[str]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Check if a table row represents an article.
        
        EMU table patterns:
        - ["Title/Ref", "1.", "Article body text"]
        - ["", "1.", "Article body text"]
        - ["Title", "1.", "(1) First clause (2) Second clause"]
        
        Returns: (is_article, article_number, article_title, article_body)
        """
        if not row or len(row) < 2:
            return False, None, None, None
        
        # Find the article number cell
        article_num = None
        article_num_idx = None
        
        for i, cell in enumerate(row):
            cell_stripped = cell.strip()
            match = ARTICLE_RE.match(cell_stripped)
            if match:
                article_num = match.group(1)
                article_num_idx = i
                break
        
        if not article_num:
            return False, None, None, None
        
        # Extract title (cell before article number, if meaningful)
        article_title = None
        if article_num_idx > 0:
            potential_title = row[article_num_idx - 1].strip()
            # Filter out reference numbers and dates (VYK, SEN, etc.)
            if potential_title and len(potential_title) > 2:
                # Check if it's mostly a reference (contains VYK, SEN, dates)
                ref_patterns = r'(VYK|SEN|R\.G\.|EK\s+\d|A\.E\.|^\d{2}\.\d{2}\.\d{4})'
                # If it's NOT just references, use it as title
                cleaned_title = re.sub(ref_patterns, '', potential_title).strip()
                if cleaned_title and len(cleaned_title) > 2:
                    # Remove any leading/trailing punctuation
                    cleaned_title = cleaned_title.strip('.,;: ')
                    if cleaned_title:
                        article_title = cleaned_title
        
        # Extract body (cells after article number)
        body_parts = []
        for i in range(article_num_idx + 1, len(row)):
            cell_text = row[i].strip()
            if cell_text:
                body_parts.append(cell_text)
        
        article_body = " ".join(body_parts) if body_parts else None
        
        return True, article_num, article_title, article_body
    
    def _is_sub_clause_row(self, row: List[str]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if a table row is a sub-clause like (1), (2), (A), (B).
        
        Patterns:
        - ["", "(1)", "Clause text"]
        - ["(1)", "Clause text"]
        - ["SEN ref", "", "(1)", "Clause text"]
        
        Returns: (is_sub_clause, clause_marker, clause_body)
        """
        if not row:
            return False, None, None
        
        # Look for clause markers like (1), (2), (A), (B), (a), (b)
        clause_re = re.compile(r"^\((\d+|[A-Za-z])\)$")
        
        clause_marker = None
        clause_idx = None
        
        for i, cell in enumerate(row):
            cell_stripped = cell.strip()
            if clause_re.match(cell_stripped):
                clause_marker = cell_stripped
                clause_idx = i
                break
        
        if not clause_marker:
            return False, None, None
        
        # Extract body (cells after clause marker)
        body_parts = []
        for i in range(clause_idx + 1, len(row)):
            cell_text = row[i].strip()
            if cell_text:
                body_parts.append(cell_text)
        
        clause_body = " ".join(body_parts) if body_parts else None
        
        return True, clause_marker, clause_body
    
    def _is_empty_row(self, row: List[str]) -> bool:
        """Check if row is effectively empty."""
        return all(len(cell.strip()) < 3 for cell in row)
    
    def _is_grade_row(self, row: List[str]) -> bool:
        """Check if a row looks like grade table data (A+, B-, 4.00, etc.)."""
        if not row or len(row) < 2:
            return False
        
        # Grade patterns: letter grades, coefficients
        grade_pattern = re.compile(r'^[A-FUWSINGa-f][+÷\-]?$|^\d+\.\d{2}$|^(SATISFACTORY|FAIL|PASS|INCOMPLETE|WITHDRAWAL)$', re.IGNORECASE)
        
        grade_cells = 0
        for cell in row:
            cell_stripped = cell.strip()
            if grade_pattern.match(cell_stripped):
                grade_cells += 1
        
        # If multiple cells look like grades/coefficients, it's a grade row
        return grade_cells >= 2
    
    def _is_pure_data_table(self, table: TableBlock) -> bool:
        """
        Determine if a table is PURELY data (no articles inside).
        
        Returns True only if the table has NO article rows.
        """
        if not table.rows or len(table.rows) < 2:
            return False
        
        # Check if ANY row contains an article - if so, it's not a pure data table
        for row in table.rows:
            is_article, _, _, _ = self._is_article_row(row)
            if is_article:
                return False
        
        # Check if it looks like a grade/coefficient table
        grade_rows = sum(1 for row in table.rows if self._is_grade_row(row))
        if grade_rows >= 3:
            return True
        
        # Check for header row with data keywords
        if table.rows:
            first_row_text = " ".join(table.rows[0]).lower()
            data_keywords = ['grade', 'coefficient', 'credit', 'hours', 'ects']
            if any(kw in first_row_text for kw in data_keywords):
                return True
        
        return False
    
    def normalize_blocks(self, blocks: List[Block]) -> List[Block]:
        """
        Main normalization pass:
        1. Convert pseudo-headings (paragraphs that should be headings)
        2. Extract articles from table rows
        3. Drop empty/garbage rows
        """
        normalized: List[Block] = []
        
        for block in blocks:
            if isinstance(block, ParagraphBlock):
                # Check if this paragraph is actually a heading
                is_heading, level = self._is_pseudo_heading(block.text)
                if is_heading:
                    normalized.append(HeadingBlock(level=level, text=block.text))
                else:
                    normalized.append(block)
            
            elif isinstance(block, TableBlock):
                # Process table - always try to extract articles, keep only pure data rows
                if self._is_pure_data_table(block):
                    # Pure data table with no articles - keep intact
                    normalized.append(block)
                else:
                    # Extract articles and sub-clauses, keeping data rows as separate table
                    extracted = self._extract_from_table(block)
                    normalized.extend(extracted)
            
            else:
                # Keep other blocks as-is
                normalized.append(block)
        
        return normalized
    
    def _extract_from_table(self, table: TableBlock) -> List[Block]:
        """
        Extract articles and paragraphs from a layout table.
        Also preserves grade data rows as a separate table.
        """
        extracted: List[Block] = []
        data_rows: List[List[str]] = []  # Collect grade/data rows
        current_article_num = None
        
        for row in table.rows:
            # Skip empty rows
            if self._is_empty_row(row):
                continue
            
            # Check if it's a grade/data row - collect separately
            if self._is_grade_row(row):
                data_rows.append(row)
                continue
            
            # Check if it's an article row
            is_article, article_num, article_title, article_body = self._is_article_row(row)
            
            if is_article:
                current_article_num = article_num
                
                # Create article heading
                if article_title:
                    heading_text = f"Article {article_num} – {article_title}"
                else:
                    heading_text = f"Article {article_num}"
                
                extracted.append(HeadingBlock(level=3, text=heading_text))
                
                # Add article body if present
                if article_body:
                    extracted.append(ParagraphBlock(text=article_body))
                continue
            
            # Check if it's a sub-clause row
            is_clause, clause_marker, clause_body = self._is_sub_clause_row(row)
            
            if is_clause and clause_body:
                # Format as paragraph with clause marker
                extracted.append(ParagraphBlock(text=f"{clause_marker} {clause_body}"))
                continue
            
            # Otherwise, join non-empty cells as a paragraph (or heading if it looks like one)
            non_empty = [c.strip() for c in row if c.strip() and len(c.strip()) > 2]
            if non_empty:
                # Filter out pure reference cells (VYK, SEN dates only)
                ref_pattern = r'^(VYK|SEN|R\.G\.)?\s*\d{2}[\./]\d{2}[\./]\d{2,4}'
                meaningful = [c for c in non_empty if not re.match(ref_pattern, c)]
                
                if meaningful:
                    text = " ".join(meaningful)
                    # Skip if it looks like just reference numbers
                    if len(text) > 10:
                        # Check if this should be a heading
                        is_heading, level = self._is_pseudo_heading(text)
                        if is_heading:
                            extracted.append(HeadingBlock(level=level, text=text))
                        else:
                            extracted.append(ParagraphBlock(text=text))
        
        # If we collected data rows, add them as a separate table
        if len(data_rows) >= 2:
            extracted.append(TableBlock(rows=data_rows, has_header=True))
        
        return extracted


class StructuredScraper:
    """
    Scrapes HTML and extracts structured blocks.
    Includes normalization to recover structure from Word HTML.
    """
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.normalizer = BlockNormalizer()
    
    def fetch_html(self, link: str) -> Optional[str]:
        """Fetch HTML content with Turkish encoding fix."""
        full_url = urljoin(self.base_url, link)
        try:
            response = requests.get(full_url, timeout=30)
            # Fix Turkish character corruption
            response.encoding = 'windows-1254'
            return response.text
        except Exception as e:
            print(f"[ERROR] Failed to fetch {link}: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Clean up text content: normalize whitespace, strip."""
        if not text:
            return ""
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_table(self, table_tag: Tag) -> TableBlock:
        """Extract table as list of rows (list of cells)."""
        rows = []
        has_header = False
        
        for tr in table_tag.find_all('tr'):
            cells = []
            # Check for header cells
            th_cells = tr.find_all('th')
            td_cells = tr.find_all('td')
            
            if th_cells:
                has_header = True
                for th in th_cells:
                    cells.append(self._clean_text(th.get_text()))
            else:
                for td in td_cells:
                    cells.append(self._clean_text(td.get_text()))
            
            if cells:  # Only add non-empty rows
                rows.append(cells)
        
        return TableBlock(rows=rows, has_header=has_header)
    
    def _extract_list(self, list_tag: Tag) -> ListBlock:
        """Extract list items from ul/ol."""
        items = []
        ordered = list_tag.name == 'ol'
        
        for li in list_tag.find_all('li', recursive=False):
            text = self._clean_text(li.get_text())
            if text:
                items.append(text)
        
        return ListBlock(items=items, ordered=ordered)
    
    def _get_heading_level(self, tag: Tag) -> int:
        """Extract heading level from h1-h6 tag."""
        if tag.name and tag.name.startswith('h') and len(tag.name) == 2:
            try:
                return int(tag.name[1])
            except ValueError:
                pass
        return 2  # Default to h2
    
    def _extract_blocks(self, soup: BeautifulSoup) -> List[Block]:
        """
        Extract structural blocks from parsed HTML.
        Preserves block type information.
        """
        blocks: List[Block] = []
        
        # Remove garbage elements
        for element in soup(["script", "style", "meta", "link", "o:p", "head"]):
            element.decompose()
        
        # Find the body or main content
        body = soup.find('body') or soup
        
        # Process all direct children and nested elements
        for element in body.descendants:
            if isinstance(element, NavigableString):
                continue
            if not isinstance(element, Tag):
                continue
            
            # Skip if this element is inside another block-level element we'll process
            if element.find_parent(['table', 'ul', 'ol']):
                continue
            
            tag_name = element.name.lower() if element.name else ""
            
            # Headings (h1-h6)
            if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = self._clean_text(element.get_text())
                if text:
                    level = self._get_heading_level(element)
                    blocks.append(HeadingBlock(level=level, text=text))
            
            # Tables
            elif tag_name == 'table':
                table_block = self._extract_table(element)
                if table_block.rows:  # Only add non-empty tables
                    blocks.append(table_block)
            
            # Lists
            elif tag_name in ['ul', 'ol']:
                list_block = self._extract_list(element)
                if list_block.items:  # Only add non-empty lists
                    blocks.append(list_block)
            
            # Paragraphs and divs with direct text content
            elif tag_name in ['p', 'div']:
                # Only process if it has direct text (not just nested elements)
                text = self._clean_text(element.get_text())
                if text and len(text) > 2:  # Skip very short/empty
                    # Avoid duplicating content from child blocks
                    has_block_children = element.find(['table', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    if not has_block_children:
                        blocks.append(ParagraphBlock(text=text))
        
        return blocks
    
    def _is_disclaimer(self, text: str) -> bool:
        """Check if text is a disclaimer, not a title."""
        text_lower = text.lower()
        for pattern in DISCLAIMER_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def _is_section_header(self, text: str) -> bool:
        """Check if text is a section header (I. GENERAL PROVISIONS) not a document title."""
        text_stripped = text.strip()
        # Roman numeral section headers
        if re.match(r'^[IVX]+\.\s+', text_stripped):
            return True
        return False
    
    def _extract_document_title(self, blocks: List[Block]) -> Optional[str]:
        """Extract document title from blocks, preferring regulatory titles over section headers."""
        title_keywords = ["regulation", "rules", "principles", "by-law", "bylaw", "code", "statute"]
        
        # FIRST: Check paragraphs for explicit title patterns (highest priority)
        for block in blocks:
            if isinstance(block, ParagraphBlock):
                text = block.text.strip()
                if self._is_disclaimer(text):
                    continue
                if len(text) < 100:
                    text_lower = text.lower()
                    # "Regulation for X" or "Rules for X" pattern (must have "for")
                    # Skip "Regulation under Article X" which is a reference, not a title
                    if ("regulation for" in text_lower or "rules for" in text_lower or
                        "regulations for" in text_lower):
                        return text
        
        # SECOND: Try headings with regulatory keywords (skip section headers)
        for block in blocks:
            if isinstance(block, HeadingBlock) and block.level <= 2:
                if not self._is_disclaimer(block.text):
                    if self._is_section_header(block.text):
                        continue  # Skip section headers like "I. GENERAL PROVISIONS"
                    # Skip generic university names
                    if block.text.strip().upper() in ["EASTERN MEDITERRANEAN UNIVERSITY", "EASTERN MEDITERRANEAN UNIVERISTY"]:
                        continue
                    # Prefer headings with regulatory keywords
                    if any(kw in block.text.lower() for kw in title_keywords):
                        return block.text
        
        # THIRD: Any heading with regulatory content
        for block in blocks:
            if isinstance(block, HeadingBlock) and block.level <= 2:
                if not self._is_disclaimer(block.text) and not self._is_section_header(block.text):
                    if block.text.strip().upper() not in ["EASTERN MEDITERRANEAN UNIVERSITY", "EASTERN MEDITERRANEAN UNIVERISTY"]:
                        return block.text
        
        # FOURTH: Fallback to ALL CAPS paragraphs with keywords
        for block in blocks:
            if isinstance(block, ParagraphBlock):
                text = block.text.strip()
                if self._is_disclaimer(text):
                    continue
                if len(text) < 100:
                    alpha = [c for c in text if c.isalpha()]
                    if alpha:
                        upper_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
                        if upper_ratio > 0.7:
                            if any(kw in text.lower() for kw in title_keywords):
                                return text
        
        return None
    
    def scrape_document(self, link: str) -> Optional[StructuredDocument]:
        """
        Scrape a single document and return normalized structured blocks.
        Implements Step 1 of the pipeline.
        """
        print(f"Scraping: {link}...")
        
        html = self.fetch_html(link)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Step 1a: Extract raw blocks
        raw_blocks = self._extract_blocks(soup)
        
        if not raw_blocks:
            print(f"  [WARN] No blocks extracted from {link}")
            return None
        
        # Step 1b: Normalize blocks (recover structure from Word HTML)
        normalized_blocks = self.normalizer.normalize_blocks(raw_blocks)
        
        # Extract title from normalized blocks
        title = self._extract_document_title(normalized_blocks)
        
        doc = StructuredDocument(
            source=link,
            document_title=title,
            blocks=normalized_blocks
        )
        
        # Count block types for logging
        headings = sum(1 for b in normalized_blocks if isinstance(b, HeadingBlock))
        paragraphs = sum(1 for b in normalized_blocks if isinstance(b, ParagraphBlock))
        tables = sum(1 for b in normalized_blocks if isinstance(b, TableBlock))
        
        print(f"  Extracted {len(normalized_blocks)} blocks: {headings} headings, {paragraphs} paragraphs, {tables} tables")
        print(f"  Title: {title}")
        
        return doc
    
    def scrape_all(self, delay: float = 1.0) -> List[StructuredDocument]:
        """
        Scrape all regulation documents.
        Returns list of StructuredDocument objects.
        """
        documents = []
        
        for link in HTM_LINKS:
            doc = self.scrape_document(link)
            if doc:
                documents.append(doc)
            time.sleep(delay)  # Respectful delay
        
        print(f"\n[OK] Scraped {len(documents)} documents")
        return documents


def detect_article_boundary(block: Block) -> Optional[str]:
    """
    Step 2: Detect if a block marks an article boundary.
    Returns article number if boundary, None otherwise.
    
    Only applies to heading blocks.
    """
    if not isinstance(block, HeadingBlock):
        return None
    
    # Match "Article X" or "Article X – Title"
    match = re.search(r"Article\s+(\d+[A-Za-z]?)", block.text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


def save_structured_documents(documents: List[StructuredDocument], output_dir: str = "rag_docs/"):
    """Save structured documents to JSON files for inspection/debugging."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for doc in documents:
        # Convert to serializable dict
        doc_dict = {
            "source": doc.source,
            "document_title": doc.document_title,
            "blocks": []
        }
        
        for block in doc.blocks:
            if isinstance(block, HeadingBlock):
                doc_dict["blocks"].append({
                    "type": "heading",
                    "level": block.level,
                    "text": block.text
                })
            elif isinstance(block, ParagraphBlock):
                doc_dict["blocks"].append({
                    "type": "paragraph",
                    "text": block.text
                })
            elif isinstance(block, TableBlock):
                doc_dict["blocks"].append({
                    "type": "table",
                    "rows": block.rows,
                    "has_header": block.has_header
                })
            elif isinstance(block, ListBlock):
                doc_dict["blocks"].append({
                    "type": "list",
                    "items": block.items,
                    "ordered": block.ordered
                })
        
        # Save to JSON
        filename = doc.source.replace('.htm', '.json').replace('%20', '_')
        filepath = output_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(doc_dict, f, ensure_ascii=False, indent=2)
        
        print(f"Saved: {filepath}")


if __name__ == "__main__":
    scraper = StructuredScraper()
    documents = scraper.scrape_all()
    
    # Save to JSON for inspection
    save_structured_documents(documents)
    
    print("\n[OK] Structured documents saved to rag_docs/")
