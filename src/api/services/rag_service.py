from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import uuid
import re
from llama_index.core.llms import ChatMessage, MessageRole
from src.api.schemas.rag import SourceDocument, RetrievalResult
from src.core.settings import settings

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession
    from src.api.models.user import User
    from src.api.dependencies.clients import RAGClients


class RAGService:
    SYSTEM_PROMPT = """
        You are a university assistant answering questions strictly based on Eastern Mediterranean University regulations.

        Rules:
        - Use ONLY the provided context to answer the question.
        - Do NOT use outside knowledge or assumptions.
        - Answer in the same language as the question.
        - When answering, explicitly cite the relevant Article number(s) and quote the exact wording when possible.
        - If multiple articles are relevant, list each separately.
        - If the context does not contain enough information, say "I don't know" and explain what is missing.

        Context:
        ---
        {context}
        ---
    """

    def __init__(self, rag_clients: "RAGClients"):
        self.clients = rag_clients

    async def retrieve_context(self, query: str, top_k: int = 5) -> RetrievalResult:
        fetch_k = settings.retrieval_top_k if self.clients.reranker.enabled else top_k
        
        retriever = self.clients.qdrant.get_retriever(top_k=fetch_k)
        nodes = await retriever.aretrieve(query)
        
        nodes = self.clients.reranker.rerank_items(
            query, nodes, 
            key=lambda n: n.node.get_content(), 
            top_k=top_k
        )
        
        sources = [self._node_to_source(node, rank) for rank, node in enumerate(nodes, 1)]
        context = "\n\n---\n\n".join(n.node.get_content() for n in nodes) or "No relevant context found"
        
        return RetrievalResult(context=context, sources=sources)

    def _node_to_source(self, node, rank: int) -> SourceDocument:
        meta = node.node.metadata
        source = meta.get('source', 'Unknown')
        article_num = meta.get('article_number')
        article_title = meta.get('article_title') or meta.get('title')
        doc_type = meta.get('type', '')
        
        if article_num and article_title:
            title = f"Article {article_num}: {article_title}"
        elif article_title:
            title = article_title
        else:
            title = self._format_source_name(source)
        
        article = f"{doc_type.title()} - Article {article_num}" if article_num else doc_type.title()
        
        return SourceDocument(rank=rank, source=source, title=title, article=article)

    def _format_source_name(self, source: str) -> str:
        name = source.replace('.md', '')
        parts = [p for p in re.split(r'[-_]', name) if p and not p.isdigit()]
        return ' '.join(word.capitalize() for word in parts) if parts else name

    def _build_messages(self, query: str, context: str, history: list[ChatMessage] | None = None):
        messages = [ChatMessage(content=self.SYSTEM_PROMPT.format(context=context), role=MessageRole.SYSTEM)]
        if history:
            messages.extend(history)
        messages.append(ChatMessage(content=query, role=MessageRole.USER))
        return messages

    async def generate_response(
        self, 
        query: str, 
        session_id: uuid.UUID,
        user: Optional["User"] = None,
        db: Optional["AsyncSession"] = None,
        top_k: int = 5
    ):
        chat_history = self.clients.chat_history
        
        history = await chat_history.get_messages(session_id, user)
        retrieval = await self.retrieve_context(query, top_k)
        messages = self._build_messages(query, retrieval.context, history)


        await chat_history.add_message(
            session_id, 
            ChatMessage(content=query, 
            role=MessageRole.USER), user
        )
        
        llm = self.clients.llm.get_llm()
        stream = await llm.astream_chat(messages)
        
        full_answer = ""
        async for chunk in stream:
            token = chunk.delta
            full_answer += token
            yield {"type": "token", "content": token}

        yield {
            "type": "final_response",
            "answer": full_answer,
            "sources": [s.model_dump() for s in retrieval.sources], 
            "query": query,
            "session_id": str(session_id),
            "has_answer": "don't know" not in full_answer.lower()
        }

        await chat_history.add_message(session_id, ChatMessage(content=full_answer, role=MessageRole.ASSISTANT), user)

        if user and db:
            await chat_history.sync_to_postgres(session_id, user, db, title=query[:100])
