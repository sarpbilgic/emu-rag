from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List
import uuid
from llama_index.core.llms import ChatMessage, MessageRole
from src.api.schemas.rag import RAGResponse, SourceDocument, RetrievalResult

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession
    from src.api.models.user import User
    from src.api.dependencies.clients import RAGClients

class RAGService:
    SYSTEM_PROMPT = (
        "You are a helpful assistant for Eastern Mediterranean University regulations.\n"
        "Your task is to answer questions based on the university regulation documents provided below.\n\n"
        "Guidelines:\n"
        "- Carefully read through all provided context sections\n"
        "- Answer the question in the same language as the question\n"
        "- If the context contains relevant information, provide a clear and explanatory answer\n"
        "- Quote specific articles, rules, or sections when applicable\n"
        "- Only say 'I don't know' if the context truly does not contain relevant information\n\n"
        "Context from university regulations:\n"
        "---\n"
        "{context}\n"
        "---"
    )

    def __init__(self, rag_clients: "RAGClients"):
        self.clients = rag_clients

    def _build_messages(
        self, 
        query: str, 
        context: str, 
        history: Optional[List[ChatMessage]] = None
    ) -> List[ChatMessage]:
        messages = [
            ChatMessage(
                content=self.SYSTEM_PROMPT.format(context=context),
                role=MessageRole.SYSTEM
            )
        ]
        if history:
            messages.extend(history)
        messages.append(ChatMessage(content=query, role=MessageRole.USER))
        return messages

    async def retrieve_context(self, query: str, top_k: int = 5) -> RetrievalResult:
        retriever = self.clients.qdrant.get_retriever(top_k=top_k)
        nodes = await retriever.aretrieve(query)
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
    
    async def generate_response(
        self, 
        query: str, 
        session_id: uuid.UUID,
        user: Optional["User"] = None,
        db: Optional["AsyncSession"] = None,
        top_k: int = 5
    ) -> RAGResponse:

        chat_history = self.clients.chat_history
        
        history = await chat_history.get_messages(session_id, user)
        retrieval_result = await self.retrieve_context(query, top_k)
        messages = self._build_messages(query, retrieval_result.context, history)

        llm = self.clients.llm.get_llm()
        stream = await llm.astream_chat(messages)
        await chat_history.add_message(
            session_id, 
            ChatMessage(content=query, role=MessageRole.USER), 
            user
        )
        full_answer = ""
        async for chunk in stream:
            token = chunk.delta
            full_answer += token
            yield {"type": "token", "content": token}

        yield {
            "type": "final_response",
            "answer": full_answer,
            "sources": [s.model_dump() for s in retrieval_result.sources], 
            "query": query,
            "session_id": str(session_id),
            "has_answer": "don't know" not in full_answer.lower()
        }

        await chat_history.add_message(session_id, ChatMessage(content=full_answer, role=MessageRole.ASSISTANT), user)

        if user and db:
            await chat_history.sync_to_postgres(session_id, user, db, title=query[:100])




       

