"""
Production-grade markdown ingestion pipeline for EMU regulations.
Uses MarkdownNodeParser for automatic header hierarchy preservation.
"""
import re
import time
from pathlib import Path
from typing import List, Dict, Callable

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

from src.core.dependencies import get_embedding_client, get_qdrant_client

logger = logging.getLogger(__name__)


class MetadataEnricher(TransformComponent):
    """Custom transformation to add article/section metadata to nodes."""
    
    def __call__(self, nodes: List[BaseNode], **kwargs) -> List[BaseNode]:
        for i, node in enumerate(nodes):
            # Extract article numbers if present
            article_match = re.search(r'\*\*Article\s+(\d+[A-Za-z]?):?\*\*', node.text)
            if article_match:
                node.metadata["article_number"] = article_match.group(1)
            
            # Extract section headers  
            section_match = re.search(r'\*\*(?:PART|SECTION)\s+([A-Z\s]+)\*\*', node.text)
            if section_match:
                node.metadata["section"] = section_match.group(1).strip()
            
            # Detect if chunk contains a table
            if "|---|" in node.text or "| " in node.text:
                node.metadata["contains_table"] = True
            
            # Add chunk index
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
            metadata["document_name"] = "EMU Statute"
        elif "regulation" in filename:
            metadata["type"] = "regulation"
        elif "rules" in filename:
            metadata["type"] = "rules"
        elif "principle" in filename:
            metadata["type"] = "principles"
            
        # Extract title from first heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1).strip()
        
        # Detect if document contains tables
        if "|---|" in content or "|--" in content:
            metadata["has_tables"] = True
            metadata["table_count"] = content.count("|---|")
        
        return metadata
    
    def create_ingestion_pipeline(self) -> IngestionPipeline:
        """
        Create LlamaIndex ingestion pipeline with:
        1. MarkdownNodeParser - auto-extracts header hierarchy as metadata
        2. MetadataEnricher - adds article/section/table detection
        3. Embedding model - embeds chunks
        """
        # Get clients
        qdrant_manager = get_qdrant_client()
        vector_store = qdrant_manager.get_vector_store()
        embed_model = get_embedding_client().get_embed_model()
        
        pipeline = IngestionPipeline(
            transformations=[
                # MarkdownNodeParser auto-adds header_path metadata
                MarkdownNodeParser(),
                # Custom metadata enrichment
                SentenceSplitter(chunk_size=1024, chunk_overlap=100),
                MetadataEnricher(),
                # Embedding (must be last transformation)
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
        """
        Process a batch of documents with automatic retry logic.
        
        Uses tenacity for exponential backoff retry on failures.
        """
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing batch {batch_num}/{total_batches}")
        logging.info(f"Documents: {[doc.metadata['source'] for doc in batch]}")
        logging.info(f"{'='*60}")
        
        # Run the pipeline for this batch
        nodes = pipeline.run(documents=batch, show_progress=True)
        logging.info(f"Batch {batch_num} completed: {len(nodes)} nodes created")
        
        return nodes
    
    def ingest_documents(self, documents: List[Document], batch_size: int = 5) -> List[BaseNode]:
        """
        Ingest documents into Qdrant using the pipeline in batches.
        
        Args:
            documents: List of documents to ingest
            batch_size: Number of documents to process per batch (default: 5)
                       Using local HuggingFace embeddings, no API rate limits
        
        Returns:
            List of all ingested nodes
        """
        qdrant_manager = get_qdrant_client()
        
        logging.info("\nStarting batched ingestion pipeline...")
        logging.info(f"Target collection: {qdrant_manager.collection_name}")
        logging.info(f"Batch size: {batch_size} document(s) per batch")
        logging.info(f"Total documents: {len(documents)}")
        logging.info(f"Estimated batches: {(len(documents) + batch_size - 1) // batch_size}")
        logging.info("Using local FastEmbed embeddings (no API rate limits)")
        
        pipeline = self.create_ingestion_pipeline()
        all_nodes = []
        
        # Process documents in batches
        total_batches = (len(documents) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(documents), batch_size):
            batch = documents[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1
            
            try:
                # Process batch with automatic retry via tenacity
                nodes = self._process_batch_with_retry(
                    pipeline=pipeline,
                    batch=batch,
                    batch_num=batch_num,
                    total_batches=total_batches
                )
                all_nodes.extend(nodes)
                
                # Small delay between batches for stability
                if batch_idx + batch_size < len(documents):
                    delay = 1  # 1 second between batches
                    print(f"⏳ Waiting {delay}s before next batch...")
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"\n✗ Batch {batch_num} failed after all retries: {e}")
                raise
        
        logging.info(f"\n{'='*60}")
        logging.info(f"[OK] Successfully ingested {len(all_nodes)} total nodes into Qdrant")
        logging.info(f"{'='*60}")
        return all_nodes


def main():
    """Main ingestion script."""
    logging.info("=" * 60)
    logging.info("EMU RAG - Markdown Ingestion Pipeline")
    logging.info("=" * 60)
    
    processor = EMUMarkdownProcessor()
    documents = processor.load_markdown_files()
    
    if not documents:
        logging.error("[ERROR] No markdown files found in emu_rag_data/")
        return
    
    # Show summary
    logging.info("\n" + "=" * 60)
    logging.info("Document Summary:")
    logging.info("=" * 60)
    for doc in documents:
        logging.info(f"  - {doc.metadata['source']}")
        logging.info(f"    Type: {doc.metadata.get('type', 'unknown')}")
        logging.info(f"    Title: {doc.metadata.get('title', 'N/A')[:50]}...")
        logging.info(f"    Tables: {doc.metadata.get('table_count', 0)}")
    
    # Clear existing vectors before ingestion
    logging.info("\n" + "=" * 60)
    logging.info("Clearing existing collection...")
    logging.info("=" * 60)
    qdrant = get_qdrant_client()
    qdrant.clear_collection()
    
    # Run ingestion with batching
    try:
        # Process 5 documents at a time (local embeddings, no API limits)
        nodes = processor.ingest_documents(documents, batch_size=5)
        
        logging.info("\n" + "=" * 60)
        logging.info("[OK] INGESTION COMPLETE")
        logging.info("=" * 60)
        logging.info(f"Documents processed: {len(documents)}")
        logging.info(f"Chunks created: {len(nodes)}")
        
        # Show sample metadata from first node
        if nodes:
            logging.info(f"\nSample chunk metadata:")
            for key, value in list(nodes[0].metadata.items())[:8]:
                print(f"  {key}: {value}")
        
    except Exception as e:
        logging.error(f"\n[ERROR] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
