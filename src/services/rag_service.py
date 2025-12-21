from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core import ChatPromptTemplate
from llama_index.core.schema import NodeWithScore
from src.core.dependencies import RAGClients
from typing import List, Dict
from pydantic import BaseModel
from src.schemas.rag import RAGResponse, SourceDocument, RetrievalResult
import json

class RAGService:
    def __init__(self, rag_clients: RAGClients):
        self.clients = rag_clients
        self.prompt_template = ChatPromptTemplate.from_messages([
            ChatMessage(
                content="You are a helpful assistant for Eastern Mediterranean University regulations.\n"
                        "Your task is to answer questions based on the university regulation documents provided below.\n\n"
                        "Guidelines:\n"
                        "- Carefully read through all provided context sections\n"
                        "- Answer the question in the same language as the question\n"
                        "- If the context contains relevant information, provide a clear and comprehensive answer\n"
                        "- Quote specific articles, rules, or sections when applicable\n"
                        "- Only say 'I don't know' if the context truly does not contain relevant information\n\n"
                        "Context from university regulations:\n"
                        "---\n"
                        "{context_str}\n"
                        "---\n",
                role=MessageRole.SYSTEM),
            ChatMessage(
                content="{query_str}",
                role=MessageRole.USER),
            ])
    def format_prompt(self, query: str, context: str, top_k: int = 5) -> str:
        return self.prompt_template.format_messages(query_str=query, context_str=context)

    def retrieve_context(self, query: str, top_k: int = 5) -> RetrievalResult:
        retriever = self.clients.qdrant.get_retriever(top_k=top_k)
        nodes = retriever.retrieve(query)
        context = []
        sources = []
        for i, node in enumerate(nodes, 1):
            node = node.node
            metadata = node.metadata
            content = node.get_content()

            source = metadata.get('source', 'Unknown')
            
            article_num = metadata.get('article_number')
            article_title = metadata.get('article_title') or metadata.get('title')
            chunk_index = metadata.get('chunk_index')
            doc_type = metadata.get('type', '')
            
            if article_num and article_title:
                title = f"Article {article_num}: {article_title}"
            elif article_title:
                title = article_title
            else:
                title = self._format_source_name(source)
            
            article = f"{doc_type.title()} - Article {article_num}" if article_num else f"{doc_type.title()}"  

            context.append(content)
            sources.append(SourceDocument(
                rank=i,
                source=source,
                title=title,
                article=article
            ))
        
        context_text = "\n\n---\n\n".join(context) if context else "No relevant context found"

        return RetrievalResult(
            context=context_text,
            sources=sources
        )
    
    def _format_source_name(self, source: str) -> str:
        import re
        name = source.replace('.md', '')
        parts = re.split(r'[-_]', name)
        text_parts = [p for p in parts if not p.isdigit() and p]
        if text_parts:
            return ' '.join(word.capitalize() for word in text_parts)
        return name
    
    def generate_response(self, query: str, top_k: int = 5) -> RAGResponse:
        retrieval_result = self.retrieve_context(query, top_k)

        prompt = self.format_prompt(query, context=retrieval_result.context)
        llm = self.clients.llm.get_llm()
        # TODO: streaming support after frontend is ready
        response = llm.chat(prompt)

        answer = str(response.message.content)
        has_answer = "don't know" not in answer.lower()

        return RAGResponse(
            answer=answer,
            has_answer=has_answer,
            query=query,
            sources=retrieval_result.sources
        )
       

