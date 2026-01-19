"""
Production-grade markdown ingestion pipeline for EMU regulations.
Handles both text-style and table-style article formats.
"""
import re
import time
from pathlib import Path
from typing import List, Dict

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import logging

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import BaseNode, TransformComponent

from src.api.dependencies.clients import get_embedding_client, get_qdrant_client

logger = logging.getLogger(__name__)


class UniversalMarkdownCleaner(TransformComponent):
    """
    Standardizes inconsistent EMU regulations into clean Markdown headers.
    Handles both text-style (Article X) and table-style (| **X.** |) formats.
    """
    
    def __call__(self, documents: List[Document], **kwargs) -> List[Document]:
        cleaned_documents = []
        
        for doc in documents:
            text = doc.text
            new_lines = []
            
            lines = text.split('\n')
            in_header_table = False  # Track if we're in the table header
            
            for i, line in enumerate(lines):
                # Skip table separator lines (|---|---|)
                if re.match(r'^\s*\|[\s\-\|]+\|?\s*$', line):
                    in_header_table = True
                    continue
                
                # --- STRATEGY 1: Handle Table-Style Articles ---
                # Pattern: **Title** | **1.** | Content
                # or: **Brief Name** | **1.** | Eastern Mediterranean...
                table_match = re.search(
                    r'^\s*\|?\s*(?:(?:\*\*)?([^*]+)(?:\*\*)?)\s*\|\s*\*\*(\d+[A-Za-z]?)\.\*\*\s*\|\s*(.*)',
                    line
                )
                
                if table_match:
                    title_part = table_match.group(1).strip()
                    article_num = table_match.group(2)
                    content_part = table_match.group(3).strip()
                    
                    # Convert to: ### Article X: Title
                    new_lines.append(f"\n### Article {article_num}: {title_part}\n")
                    if content_part:
                        new_lines.append(content_part)
                    continue
                
                # --- STRATEGY 2: Handle Multi-column Table Rows ---
                # Pattern: | (1) | To... | Content | More |
                multi_col_match = re.search(
                    r'^\s*\|\s*\((\d+)\)\s*\|\s*(.*)',
                    line
                )
                if multi_col_match and in_header_table:
                    sub_num = multi_col_match.group(1)
                    content = multi_col_match.group(2).replace('|', ' ').strip()
                    new_lines.append(f"\n**({sub_num})** {content}")
                    continue
                
                # --- STRATEGY 3: Handle Bold-Style Articles (EMU_Statute) ---
                # Pattern: **Article 1: Title**
                if "**Article" in line:
                    line = re.sub(
                        r'\*\*(Article\s+\d+[A-Za-z]?:?\s*[^*]*)\*\*',
                        r'### \1',
                        line
                    )
                
                # --- STRATEGY 4: Handle Part/Section Headers ---
                # Pattern: **PART ONE** -> ## PART ONE
                if "**PART" in line or "**SECTION" in line or "**CHAPTER" in line:
                    line = re.sub(
                        r'\*\*((?:PART|SECTION|CHAPTER)\s+[A-Z0-9\s]+)\*\*',
                        r'## \1',
                        line
                    )
                
                # Reset table tracking if we hit a non-table line
                if line.strip() and not line.strip().startswith('|'):
                    in_header_table = False
                
                new_lines.append(line)
            
            # Create NEW document instead of modifying existing one
            # (Document.text is read-only in LlamaIndex)
            cleaned_text = '\n'.join(new_lines)
            new_doc = Document(
                text=cleaned_text,
                metadata=doc.metadata.copy(),
                id_=doc.id_
            )
            cleaned_documents.append(new_doc)
            
        return cleaned_documents


class MetadataEnricher(TransformComponent):
    """
    Extracts structured metadata from standardized chunks.
    Adds: article_number, title, section for source citations.
    """
    
    def __call__(self, nodes: List[BaseNode], **kwargs) -> List[BaseNode]:
        for i, node in enumerate(nodes):
            content = node.get_content()
            
            # 1. Extract Article Number (now standardized to "Article X")
            article_match = re.search(r'###?\s*Article\s+(\d+[A-Za-z]?)', content)
            if article_match:
                node.metadata["article_number"] = article_match.group(1)
                
                # Extract article title (text after colon)
                title_match = re.search(
                    r'###?\s*Article\s+\d+[A-Za-z]?:?\s*([^\n]+)',
                    content
                )
                if title_match:
                    node.metadata["article_title"] = title_match.group(1).strip()
            
            # 2. Extract Section/Part/Chapter
            section_match = re.search(
                r'##\s*((?:PART|SECTION|CHAPTER)\s+[A-Z0-9\s]+)',
                content
            )
            if section_match:
                node.metadata["section"] = section_match.group(1).strip()
            
            # 3. Use first header as title if article_title not found
            if "article_title" not in node.metadata:
                lines = content.strip().split('\n')
                for line in lines:
                    if line.startswith('###'):
                        node.metadata["title"] = line.replace('###', '').strip()
                        break
            else:
                # Use article title as general title
                node.metadata["title"] = node.metadata.get("article_title")
            
            # 4. Detect tables
            if "|---|" in content or "| " in content:
                node.metadata["contains_table"] = True
            
            # 5. Add chunk index
            node.metadata["chunk_index"] = i
        
        return nodes


class EMUMarkdownProcessor:
    """Process EMU regulation markdown files with automatic header extraction."""
    
    def __init__(self, data_dir: str = "emu_rag_data"):
        self.data_dir = Path(data_dir)
        
    def load_markdown_files(self) -> List[Document]:
        """Load all markdown files from data directory with metadata."""
        documents = []
        
        for md_file in self.data_dir.glob("*.md"):
            print(f"Loading: {md_file.name}")
            
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            metadata = self._extract_document_metadata(md_file, content)
            
            doc = Document(
                text=content,
                metadata=metadata,
                id_=str(md_file.stem)
            )
            documents.append(doc)
            
        logging.info(f"Loaded {len(documents)} markdown files")
        return documents
    
    def _extract_document_metadata(self, file_path: Path, content: str) -> Dict:
        """Extract document-level metadata from filename and content."""
        metadata = {
            "source": file_path.name,
            "file_path": str(file_path),
            "type": "regulation"
        }
        
        # Extract document type from filename
        filename = file_path.stem.lower()
        if "statute" in filename:
            metadata["type"] = "statute"
        elif "regulation" in filename:
            metadata["type"] = "regulation"
        elif "rules" in filename:
            metadata["type"] = "rules"
        elif "principle" in filename:
            metadata["type"] = "principles"
        elif "bylaw" in filename:
            metadata["type"] = "bylaw"
            
        # Extract title from first heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata["document_title"] = title_match.group(1).strip()
        
        # Detect if document contains tables
        if "|---|" in content or "|--" in content:
            metadata["has_tables"] = True
            metadata["table_count"] = content.count("|---|")
        
        return metadata
    
    def create_ingestion_pipeline(self) -> IngestionPipeline:
        """
        Create LlamaIndex ingestion pipeline with:
        1. UniversalMarkdownCleaner - standardizes both formats
        2. MarkdownNodeParser - splits by headers
        3. MetadataEnricher - adds article/section metadata
        4. Embedding model - embeds chunks
        """
        qdrant_manager = get_qdrant_client()
        # use_async=False for sync pipeline.run()
        vector_store = qdrant_manager.get_vector_store(enable_hybrid=True, use_async=False)
        embed_model = get_embedding_client().get_embed_model()
        
        pipeline = IngestionPipeline(
            transformations=[
                # Step 1: Fix inconsistent markdown formats
                UniversalMarkdownCleaner(),
                # Step 2: Split by headers (now standardized)
                MarkdownNodeParser(),
                # Step 3: Further chunking if needed
                SentenceSplitter(chunk_size=1024, chunk_overlap=100),
                # Step 4: Extract metadata for citations
                MetadataEnricher(),
                # Step 5: Embed (must be last)
                embed_model,
            ],
            vector_store=vector_store,
        )
        
        return pipeline
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )
    def _process_batch_with_retry(
        self, 
        pipeline: IngestionPipeline, 
        batch: List[Document],
        batch_num: int,
        total_batches: int
    ) -> List[BaseNode]:
        """Process a batch of documents with automatic retry logic."""
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing batch {batch_num}/{total_batches}")
        logging.info(f"Documents: {[doc.metadata['source'] for doc in batch]}")
        logging.info(f"{'='*60}")
        
        nodes = pipeline.run(documents=batch, show_progress=True)
        logging.info(f"Batch {batch_num} completed: {len(nodes)} nodes created")
        
        return nodes
    
    def ingest_documents(self, documents: List[Document], batch_size: int = 10) -> List[BaseNode]:
        """Ingest documents into Qdrant using the pipeline in batches."""
        qdrant_manager = get_qdrant_client()
        
        logging.info("\nStarting ingestion pipeline...")
        logging.info(f"Target collection: {qdrant_manager.collection_name}")
        logging.info(f"Batch size: {batch_size} document(s) per batch")
        logging.info(f"Total documents: {len(documents)}")
        
        pipeline = self.create_ingestion_pipeline()
        all_nodes = []
        
        total_batches = (len(documents) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(documents), batch_size):
            batch = documents[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1
            
            try:
                nodes = self._process_batch_with_retry(
                    pipeline=pipeline,
                    batch=batch,
                    batch_num=batch_num,
                    total_batches=total_batches
                )
                all_nodes.extend(nodes)
                    
            except Exception as e:
                print(f"\n✗ Batch {batch_num} failed: {e}")
                raise
        
        logging.info(f"\n[OK] Successfully ingested {len(all_nodes)} total nodes")
        return all_nodes


def main():
    """Main ingestion script."""
    logging.basicConfig(level=logging.INFO)
    logging.info("=" * 60)
    logging.info("EMU RAG - Universal Markdown Ingestion Pipeline")
    logging.info("=" * 60)
    
    processor = EMUMarkdownProcessor()
    documents = processor.load_markdown_files()
    
    if not documents:
        logging.error("[ERROR] No markdown files found in emu_rag_data/")
        return
    
    # Show summary
    logging.info("\nDocument Summary:")
    for doc in documents:
        logging.info(f"  - {doc.metadata['source']}")
        logging.info(f"    Type: {doc.metadata.get('type', 'unknown')}")
        if 'document_title' in doc.metadata:
            logging.info(f"    Title: {doc.metadata['document_title'][:50]}...")
    
    # Clear existing collection
    logging.info("\nClearing existing collection...")
    qdrant = get_qdrant_client()
    qdrant.clear_collection_sync()
    
    # Run ingestion
    try:
        nodes = processor.ingest_documents(documents, batch_size=10)
        
        logging.info("\n[OK] INGESTION COMPLETE")
        logging.info(f"Documents processed: {len(documents)}")
        logging.info(f"Chunks created: {len(nodes)}")
        
        # Show sample metadata
        if nodes:
            logging.info(f"\nSample chunk metadata:")
            sample = nodes[0].metadata
            for key in ['source', 'type', 'article_number', 'article_title', 'title', 'chunk_index']:
                if key in sample:
                    logging.info(f"  {key}: {sample[key]}")
        
    except Exception as e:
        logging.error(f"\n[ERROR] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()