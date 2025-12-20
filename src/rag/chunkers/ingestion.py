"""
Production-grade markdown ingestion pipeline for EMU regulations.
Uses MarkdownNodeParser for automatic header hierarchy preservation.
"""
import re
from pathlib import Path
from typing import List, Dict, Callable

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import BaseNode, TransformComponent

from src.core.dependencies import get_embedding_client, get_qdrant_client


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
            
            # Extract document-level metadata
            metadata = self._extract_document_metadata(md_file, content)
            
            doc = Document(
                text=content,
                metadata=metadata,
                id_=str(md_file.stem)
            )
            documents.append(doc)
            
        print(f"\n[OK] Loaded {len(documents)} markdown files")
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
                MetadataEnricher(),
                # Embedding (must be last transformation)
                embed_model,
            ],
            vector_store=vector_store,
        )
        
        return pipeline
    
    def ingest_documents(self, documents: List[Document]) -> List[BaseNode]:
        """Ingest documents into Qdrant using the pipeline."""
        qdrant_manager = get_qdrant_client()
        
        print("\nStarting ingestion pipeline...")
        print(f"Target collection: {qdrant_manager.collection_name}")
        
        pipeline = self.create_ingestion_pipeline()
        
        # Run the pipeline - handles chunking, metadata, embedding, storage
        nodes = pipeline.run(documents=documents, show_progress=True)
        
        print(f"\n[OK] Successfully ingested {len(nodes)} nodes into Qdrant")
        return nodes


def main():
    """Main ingestion script."""
    print("=" * 60)
    print("EMU RAG - Markdown Ingestion Pipeline")
    print("=" * 60)
    
    processor = EMUMarkdownProcessor()
    documents = processor.load_markdown_files()
    
    if not documents:
        print("[ERROR] No markdown files found in emu_rag_data/")
        return
    
    # Show summary
    print("\n" + "=" * 60)
    print("Document Summary:")
    print("=" * 60)
    for doc in documents:
        print(f"  - {doc.metadata['source']}")
        print(f"    Type: {doc.metadata.get('type', 'unknown')}")
        print(f"    Title: {doc.metadata.get('title', 'N/A')[:50]}...")
        print(f"    Tables: {doc.metadata.get('table_count', 0)}")
    
    # Clear existing vectors before ingestion
    print("\n" + "=" * 60)
    print("Clearing existing collection...")
    print("=" * 60)
    qdrant = get_qdrant_client()
    qdrant.clear_collection()
    
    # Run ingestion
    try:
        nodes = processor.ingest_documents(documents)
        
        print("\n" + "=" * 60)
        print("[OK] INGESTION COMPLETE")
        print("=" * 60)
        print(f"Documents processed: {len(documents)}")
        print(f"Chunks created: {len(nodes)}")
        
        # Show sample metadata from first node
        if nodes:
            print(f"\nSample chunk metadata:")
            for key, value in list(nodes[0].metadata.items())[:8]:
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"\n[ERROR] Ingestion failed: {e}")
        raise


if __name__ == "__main__":
    main()
