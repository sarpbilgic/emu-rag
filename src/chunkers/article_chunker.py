"""
Article-based chunking pipeline for EMU regulations.
Implements Steps 3-6 of the pipeline:
  Step 3: Group blocks into Article objects
  Step 4: Serialize each Article to clean text
  Step 5: Split long articles (paragraph-based)
  Step 6: Drop garbage (< 150 chars)

Input: StructuredDocument (from structured_scraper.py)
Output: List of Chunk objects ready for embedding
"""
import re
import logging
from typing import List, Optional
from dataclasses import dataclass

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from llama_index.core import Document
from llama_index.core.schema import TextNode

from src.chunkers.models import (
    StructuredDocument,
    Article,
    Chunk,
    Block,
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
    ListBlock,
)
from src.scrapers.structured_scraper import detect_article_boundary
from src.api.dependencies.clients import get_embedding_client, get_qdrant_client

logger = logging.getLogger(__name__)

# Chunk size limits
MAX_CHUNK_SIZE = 1500  # chars
MIN_CHUNK_SIZE = 150   # chars


class ArticleGrouper:
    """
    Step 3: Group blocks into Article objects.
    
    Rules:
    - When Article X heading found -> start new Article
    - All blocks until next article boundary belong to current article
    - Tables stay inside their article (never extracted separately)
    - Never merge articles
    - Never split at this stage
    """
    
    # Regex for detecting section headers (Roman numerals)
    SECTION_RE = re.compile(r'^([IVX]+\.?\s+.+)$', re.IGNORECASE)
    
    def group_into_articles(self, doc: StructuredDocument) -> List[Article]:
        """Group document blocks into Article objects."""
        articles: List[Article] = []
        current_article: Optional[Article] = None
        current_section: Optional[str] = None  # Track current section (e.g., "I. GENERAL PROVISIONS")
        preamble_blocks: List[Block] = []  # Blocks before first article
        
        for block in doc.blocks:
            # Detect section headers (Roman numeral headings at level 1)
            if isinstance(block, HeadingBlock) and block.level == 1:
                section_match = self.SECTION_RE.match(block.text)
                if section_match:
                    current_section = block.text
                    # Don't add section headers as content blocks, just track them
                    continue
            
            # Check if this block is an article boundary
            article_num = detect_article_boundary(block)
            
            if article_num:
                # Save current article if exists
                if current_article:
                    articles.append(current_article)
                
                # Extract title from heading (text after "Article X")
                title = None
                if isinstance(block, HeadingBlock):
                    # Try to extract title after article number
                    # Pattern: "Article 1: Title" or "Article 1 - Title" or "Article 1 Title"
                    title_match = re.search(
                        r'Article\s+\d+[A-Za-z]?\s*[:\-–]?\s*(.+)',
                        block.text,
                        re.IGNORECASE
                    )
                    if title_match:
                        title = title_match.group(1).strip()
                        if title and len(title) < 3:
                            title = None
                
                # Start new article with section context
                current_article = Article(
                    article_number=article_num,
                    article_title=title,
                    blocks=[],
                    source=doc.source,
                    document_title=doc.document_title,
                    section_title=current_section
                )
            elif current_article:
                # Add block to current article
                current_article.blocks.append(block)
            else:
                # Block before first article (preamble)
                preamble_blocks.append(block)
        
        # Don't forget the last article
        if current_article:
            articles.append(current_article)
        
        # If there are preamble blocks and no articles, create a "Preamble" article
        if preamble_blocks and not articles:
            articles.append(Article(
                article_number="0",
                article_title="Preamble",
                blocks=preamble_blocks,
                source=doc.source,
                document_title=doc.document_title,
                section_title=None
            ))
        elif preamble_blocks and articles:
            # Prepend preamble to first article or create separate
            # For regulations, preamble usually belongs contextually to intro
            preamble_article = Article(
                article_number="0",
                article_title="Preamble",
                blocks=preamble_blocks,
                source=doc.source,
                document_title=doc.document_title,
                section_title=None
            )
            articles.insert(0, preamble_article)
        
        return articles


class ArticleSerializer:
    """
    Step 4: Serialize each Article to clean text.
    
    Format:
        Article {number} – {title}
        Source: {source_file}
        
        {content}
    """
    
    def _render_table(self, table: TableBlock) -> str:
        """Render table as plain text grid."""
        if not table.rows:
            return ""
        
        lines = []
        
        # Calculate column widths
        col_widths = []
        for row in table.rows:
            for i, cell in enumerate(row):
                if i >= len(col_widths):
                    col_widths.append(len(cell))
                else:
                    col_widths[i] = max(col_widths[i], len(cell))
        
        # Render rows
        for row_idx, row in enumerate(table.rows):
            cells = []
            for i, cell in enumerate(row):
                width = col_widths[i] if i < len(col_widths) else len(cell)
                cells.append(cell.ljust(width))
            lines.append(" | ".join(cells))
            
            # Add separator after header
            if row_idx == 0 and table.has_header:
                separator = ["-" * w for w in col_widths]
                lines.append("-+-".join(separator))
        
        return "\n".join(lines)
    
    def _render_list(self, list_block: ListBlock) -> str:
        """Render list as plain text."""
        lines = []
        for i, item in enumerate(list_block.items, 1):
            if list_block.ordered:
                lines.append(f"{i}. {item}")
            else:
                lines.append(f"• {item}")
        return "\n".join(lines)
    
    def serialize_article(self, article: Article) -> str:
        """Convert Article to clean text for embedding."""
        lines = []
        
        # Header
        if article.article_title:
            lines.append(f"Article {article.article_number} – {article.article_title}")
        else:
            lines.append(f"Article {article.article_number}")
        
        # Include section context if available
        if article.section_title:
            lines.append(f"Section: {article.section_title}")
        
        lines.append(f"Source: {article.source}")
        lines.append("")  # Blank line after header
        
        # Content
        for block in article.blocks:
            if isinstance(block, ParagraphBlock):
                lines.append(block.text)
                lines.append("")  # Blank line between paragraphs
            elif isinstance(block, HeadingBlock):
                # Sub-heading within article
                lines.append(f"## {block.text}")
                lines.append("")
            elif isinstance(block, TableBlock):
                table_text = self._render_table(block)
                if table_text:
                    lines.append(table_text)
                    lines.append("")
            elif isinstance(block, ListBlock):
                list_text = self._render_list(block)
                if list_text:
                    lines.append(list_text)
                    lines.append("")
        
        return "\n".join(lines).strip()
    
    def get_article_header(self, article: Article) -> str:
        """Get just the header portion for chunk repetition."""
        lines = []
        
        if article.article_title:
            lines.append(f"Article {article.article_number} – {article.article_title}")
        else:
            lines.append(f"Article {article.article_number}")
        
        if article.section_title:
            lines.append(f"Section: {article.section_title}")
        
        lines.append(f"Source: {article.source}")
        lines.append("")  # Trailing newline for consistency
        
        return "\n".join(lines)


class ArticleSplitter:
    """
    Step 5: Split long articles.
    
    Rules:
    - Max chunk size: ~1200-1500 chars
    - Min chunk size: 150 chars
    - Split by paragraph groups only
    - Never split mid-sentence
    - Repeat article header in every sub-chunk
    - Tables stay intact (never split)
    """
    
    def __init__(
        self, 
        max_chunk_size: int = MAX_CHUNK_SIZE,
        min_chunk_size: int = MIN_CHUNK_SIZE
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.serializer = ArticleSerializer()
    
    def _split_into_paragraph_groups(self, article: Article) -> List[List[Block]]:
        """Split article blocks into groups that fit within chunk size."""
        groups: List[List[Block]] = []
        current_group: List[Block] = []
        current_size = 0
        header_size = len(self.serializer.get_article_header(article))
        
        for block in article.blocks:
            # Calculate block size
            if isinstance(block, ParagraphBlock):
                block_size = len(block.text) + 2  # +2 for newlines
            elif isinstance(block, TableBlock):
                block_size = len(self.serializer._render_table(block)) + 2
            elif isinstance(block, ListBlock):
                block_size = len(self.serializer._render_list(block)) + 2
            elif isinstance(block, HeadingBlock):
                block_size = len(block.text) + 5  # +5 for ## and newlines
            else:
                block_size = 0
            
            # Check if adding this block would exceed max size
            projected_size = header_size + current_size + block_size
            
            if projected_size > self.max_chunk_size and current_group:
                # Save current group and start new one
                groups.append(current_group)
                current_group = []
                current_size = 0
            
            # Tables never split - if table alone exceeds max, it still gets its own chunk
            current_group.append(block)
            current_size += block_size
        
        # Don't forget last group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def split_article(self, article: Article) -> List[Chunk]:
        """Split article into chunks, preserving structure."""
        full_text = self.serializer.serialize_article(article)
        
        # If article fits in one chunk, return as-is
        if len(full_text) <= self.max_chunk_size:
            contains_table = any(isinstance(b, TableBlock) for b in article.blocks)
            return [Chunk(
                text=full_text,
                article_number=article.article_number,
                article_title=article.article_title,
                source=article.source,
                document_title=article.document_title,
                section_title=article.section_title,
                chunk_index=0,
                total_chunks=1,
                contains_table=contains_table
            )]
        
        # Split into paragraph groups
        groups = self._split_into_paragraph_groups(article)
        header = self.serializer.get_article_header(article)
        
        chunks = []
        for i, group in enumerate(groups):
            # Create a temporary article with just this group's blocks
            temp_article = Article(
                article_number=article.article_number,
                article_title=article.article_title,
                blocks=group,
                source=article.source,
                document_title=article.document_title
            )
            
            chunk_text = self.serializer.serialize_article(temp_article)
            contains_table = any(isinstance(b, TableBlock) for b in group)
            
            chunks.append(Chunk(
                text=chunk_text,
                article_number=article.article_number,
                article_title=article.article_title,
                source=article.source,
                document_title=article.document_title,
                section_title=article.section_title,
                chunk_index=i,
                total_chunks=len(groups),
                contains_table=contains_table
            ))
        
        return chunks


class GarbageFilter:
    """
    Step 6: Drop garbage.
    
    Drop chunk if:
    - Length < 150 characters
    """
    
    def __init__(self, min_size: int = MIN_CHUNK_SIZE):
        self.min_size = min_size
    
    def filter_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Remove chunks that are too small."""
        filtered = []
        dropped = 0
        
        for chunk in chunks:
            if len(chunk.text) >= self.min_size:
                filtered.append(chunk)
            else:
                dropped += 1
                logger.debug(f"Dropped chunk (too small): {chunk.text[:50]}...")
        
        if dropped > 0:
            logger.info(f"Dropped {dropped} chunks below {self.min_size} chars")
        
        return filtered


class StructuredIngestionPipeline:
    """
    Complete pipeline: StructuredDocument -> embedded chunks in Qdrant.
    
    Combines Steps 3-6 and adds embedding + storage.
    """
    
    def __init__(self):
        self.grouper = ArticleGrouper()
        self.splitter = ArticleSplitter()
        self.filter = GarbageFilter()
    
    def process_document(self, doc: StructuredDocument) -> List[Chunk]:
        """Process a single document through the full pipeline."""
        # Step 3: Group into articles
        articles = self.grouper.group_into_articles(doc)
        logger.info(f"  Grouped into {len(articles)} articles")
        
        # Step 4 & 5: Serialize and split
        all_chunks = []
        for article in articles:
            chunks = self.splitter.split_article(article)
            all_chunks.extend(chunks)
        
        logger.info(f"  Split into {len(all_chunks)} chunks")
        
        # Step 6: Filter garbage
        filtered_chunks = self.filter.filter_chunks(all_chunks)
        logger.info(f"  After filtering: {len(filtered_chunks)} chunks")
        
        return filtered_chunks
    
    def process_documents(self, documents: List[StructuredDocument]) -> List[Chunk]:
        """Process multiple documents."""
        all_chunks = []
        
        for doc in documents:
            logger.info(f"Processing: {doc.source}")
            chunks = self.process_document(doc)
            all_chunks.extend(chunks)
        
        logger.info(f"\nTotal chunks: {len(all_chunks)}")
        return all_chunks
    
    def chunks_to_nodes(self, chunks: List[Chunk]) -> List[TextNode]:
        """Convert Chunk objects to LlamaIndex TextNode for embedding."""
        nodes = []
        
        for i, chunk in enumerate(chunks):
            metadata = {
                "source": chunk.source,
                "article_number": chunk.article_number,
                "chunk_index": chunk.chunk_index,
                "total_chunks": chunk.total_chunks,
                "contains_table": chunk.contains_table,
            }
            
            if chunk.article_title:
                metadata["article_title"] = chunk.article_title
                metadata["title"] = f"Article {chunk.article_number}: {chunk.article_title}"
            else:
                metadata["title"] = f"Article {chunk.article_number}"
            
            if chunk.document_title:
                metadata["document_title"] = chunk.document_title
            
            if chunk.section_title:
                metadata["section_title"] = chunk.section_title
            
            # Determine document type from source filename
            source_lower = chunk.source.lower()
            if "statute" in source_lower:
                metadata["type"] = "statute"
            elif "regulation" in source_lower:
                metadata["type"] = "regulation"
            elif "rules" in source_lower:
                metadata["type"] = "rules"
            elif "principle" in source_lower:
                metadata["type"] = "principles"
            elif "bylaw" in source_lower:
                metadata["type"] = "bylaw"
            else:
                metadata["type"] = "regulation"
            
            node = TextNode(
                text=chunk.text,
                metadata=metadata,
                id_=f"{chunk.source}_{chunk.article_number}_{chunk.chunk_index}"
            )
            nodes.append(node)
        
        return nodes
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )
    def _embed_batch(self, nodes: List[TextNode], embed_model) -> List[TextNode]:
        """Embed a batch of nodes with retry logic."""
        texts = [node.text for node in nodes]
        embeddings = embed_model.get_text_embedding_batch(texts)
        
        for node, embedding in zip(nodes, embeddings):
            node.embedding = embedding
        
        return nodes
    
    def ingest_to_qdrant(
        self, 
        chunks: List[Chunk], 
        batch_size: int = 10
    ) -> int:
        """Embed chunks and store in Qdrant."""
        qdrant_manager = get_qdrant_client()
        embed_client = get_embedding_client()
        embed_model = embed_client.get_embed_model()
        vector_store = qdrant_manager.get_vector_store(enable_hybrid=True, use_async=False)
        
        nodes = self.chunks_to_nodes(chunks)
        
        logger.info(f"\nIngesting {len(nodes)} nodes to Qdrant...")
        logger.info(f"Collection: {qdrant_manager.collection_name}")
        
        # Process in batches
        total_batches = (len(nodes) + batch_size - 1) // batch_size
        embedded_nodes = []
        
        for batch_idx in range(0, len(nodes), batch_size):
            batch = nodes[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1
            
            logger.info(f"Embedding batch {batch_num}/{total_batches}...")
            
            embedded_batch = self._embed_batch(batch, embed_model)
            embedded_nodes.extend(embedded_batch)
        
        # Add to vector store
        logger.info("Adding to Qdrant...")
        vector_store.add(embedded_nodes)
        
        logger.info(f"[OK] Ingested {len(embedded_nodes)} nodes")
        return len(embedded_nodes)


def main():
    """Main ingestion script."""
    logging.basicConfig(level=logging.INFO)
    logger.info("=" * 60)
    logger.info("EMU RAG - Structured HTML Ingestion Pipeline")
    logger.info("=" * 60)
    
    # Import scraper
    from src.scrapers.structured_scraper import StructuredScraper, save_structured_documents
    
    # Step 1-2: Scrape and extract structure
    scraper = StructuredScraper()
    documents = scraper.scrape_all()
    
    if not documents:
        logger.error("[ERROR] No documents scraped")
        return
    
    # Save structured JSON for inspection
    save_structured_documents(documents)
    
    # Check what's already indexed
    qdrant = get_qdrant_client()
    indexed_sources = qdrant.get_indexed_sources()
    
    logger.info(f"\nAlready indexed: {len(indexed_sources)} sources")
    
    # Filter to new documents only
    new_docs = [
        doc for doc in documents 
        if doc.source not in indexed_sources
    ]
    
    if not new_docs:
        logger.info("[OK] All documents already indexed. Nothing to do.")
        return
    
    logger.info(f"\nNew documents to process: {len(new_docs)}")
    for doc in new_docs:
        logger.info(f"  → {doc.source}")
    
    # Steps 3-6: Process and ingest
    pipeline = StructuredIngestionPipeline()
    chunks = pipeline.process_documents(new_docs)
    
    if not chunks:
        logger.error("[ERROR] No chunks generated")
        return
    
    # Show sample
    logger.info("\nSample chunk:")
    logger.info("-" * 40)
    sample = chunks[0]
    logger.info(f"Article: {sample.article_number}")
    logger.info(f"Title: {sample.article_title}")
    logger.info(f"Source: {sample.source}")
    logger.info(f"Length: {len(sample.text)} chars")
    logger.info(f"Text preview: {sample.text[:200]}...")
    logger.info("-" * 40)
    
    # Ingest to Qdrant
    count = pipeline.ingest_to_qdrant(chunks)
    
    logger.info("\n" + "=" * 60)
    logger.info("[OK] INGESTION COMPLETE")
    logger.info(f"Documents processed: {len(new_docs)}")
    logger.info(f"Chunks ingested: {count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

