---
title: Emu Rag Assistant
emoji: 🎓
colorFrom: blue
colorTo: gray
sdk: docker
pinned: false
app_port: 7860
---

# 🎓 EMU RAG Assistant

A production-ready **Retrieval-Augmented Generation (RAG)** system designed to provide intelligent, context-aware answers about Eastern Mediterranean University (EMU) regulations, statutes, and academic policies. Built with modern Python async architecture and deployed on HuggingFace Spaces.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Deployment](#deployment)

## 🎯 Overview

The EMU RAG Assistant is an intelligent question-answering system that helps students, faculty, and staff quickly find accurate information from university regulations. By leveraging RAG technology, the system combines the power of large language models with a comprehensive knowledge base of EMU documents, ensuring responses are both accurate and grounded in official university sources.

### Key Capabilities

- **Semantic Search**: Advanced vector search through university regulations using embeddings
- **Context-Aware Responses**: LLM-powered answers with source citations
- **Multi-language Support**: Answers in the same language as the question
- **Session Management**: Persistent chat sessions with conversation history
- **Dual Authentication**: Microsoft OAuth and local email/password authentication
- **Rate Limiting**: Protection against abuse with separate limits for authenticated and anonymous users

## ✨ Features

### 🔍 Intelligent Retrieval
- **Vector Search**: Uses Qdrant vector database for semantic similarity search
- **Metadata Filtering**: Advanced filtering by document type, article numbers, and sections
- **Top-K Retrieval**: Configurable number of relevant document chunks per query

### 💬 Conversational Interface
- **Chat Sessions**: Persistent conversation threads with unique session IDs
- **History Management**: Redis caching for fast access, PostgreSQL for persistence
- **Context Preservation**: Maintains conversation context across multiple turns

### 🔐 Authentication & Authorization
- **Microsoft OAuth**: Single Sign-On (SSO) integration for EMU users
- **Local Authentication**: Email/password registration and login
- **JWT Tokens**: Secure token-based authentication with configurable expiration
- **Token Blacklisting**: Secure logout with Redis-based token invalidation

### 📊 Data Management
- **Document Ingestion**: Automated processing of markdown documents
- **Chunking Strategy**: Intelligent document segmentation preserving article structure
- **Metadata Extraction**: Automatic extraction of article numbers, titles, and sections

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────┐
│   FastAPI App   │
│     │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬─────────────┐
    │         │              │             │
┌───▼───┐ ┌──▼───┐    ┌─────▼─────┐  ┌────▼────┐
│PostgreSQL│ │ Redis │    │  Qdrant  │  │   LLM   │
│          │ │       │    │  Vector  │  │  (xAI)  │
│  Users   │ │ Cache │    │   Store  │  │         │
│ Sessions │ │ Rate  │    │Embeddings│  │         │
│ Messages │ │ Limit │    │          │  │         │
└──────────┘ └───────┘    └──────────┘  └─────────┘
```

### Request Flow

1. **User Query** → FastAPI endpoint receives query with optional session ID
2. **Authentication** → JWT token validation (optional for anonymous users)
3. **Context Retrieval** → Query embedding → Qdrant vector search → Top-K relevant chunks
4. **LLM Generation** → Context + conversation history → LLM → Response generation
5. **Response** → Answer + source citations + session ID
6. **Storage** → Messages cached in Redis, synced to PostgreSQL

### Data Flow

```
Document Ingestion:
Markdown Files → Chunking → Embeddings → Qdrant Vector Store

Query Processing:
User Query → Embedding → Vector Search → Context Retrieval → LLM → Response

Session Management:
Messages → Redis (Fast Cache) → PostgreSQL (Persistence)
```

## 🛠️ Tech Stack

### Backend Framework
- **FastAPI**: Modern, fast web framework for building APIs
- **Uvicorn**: ASGI server for async Python applications
- **Pydantic**: Data validation using Python type annotations

### AI/ML Stack
- **LlamaIndex**: Framework for LLM applications and data ingestion
- **xAI (Grok)**: Large Language Model for response generation
- **FastEmbed**: Fast embedding generation for semantic search
- **Qdrant**: Vector database for similarity search

### Data Storage
- **PostgreSQL**: Primary database for users, sessions, and messages
- **Redis**: Caching layer for chat history and rate limiting
- **SQLModel**: ORM for SQL databases in Python, designed for simplicity and compatibility

### Authentication
- **python-jose**: JWT token encoding/decoding
- **passlib**: Password hashing (bcrypt)
- **fastapi-sso**: Microsoft OAuth integration

### Infrastructure
- **Alembic**: Database migration tool
- **Docker**: Containerization for deployment
- **HuggingFace Spaces**: Cloud deployment platform

## 📡 API Documentation

### Base URL
```
https://sarpbilgic-emu-rag.hf.space
```

### Interactive API Docs
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

### Main Endpoints

#### RAG Endpoints
- `POST /api/v1/rag/ask` - Submit a query and get AI-generated response
  - Query parameters: `query` (required)
  - Headers: `X-Session-Id` (optional), `Authorization: Bearer <token>` (optional)
  - Response: Answer, sources, session ID

#### Authentication Endpoints
- `POST /api/v1/auth/register` - Register new user (email/password)
- `POST /api/v1/auth/login` - Login with email/password
- `POST /api/v1/auth/logout` - Logout and invalidate token
- `GET /api/v1/auth/microsoft/login` - Initiate Microsoft OAuth flow
- `GET /api/v1/auth/microsoft/callback` - OAuth callback handler

#### User Endpoints
- `GET /api/v1/user/me` - Get current user information (authenticated)

#### Session Endpoints
- `GET /api/v1/sessions` - List user's chat sessions
- `GET /api/v1/sessions/{session_id}/messages` - Get messages for a session

## 📁 Project Structure

```
emu-rag/
├── src/
│   ├── api/                    # FastAPI application
│   │   ├── routers/           # API route handlers
│   │   │   ├── rag.py         # RAG query endpoint
│   │   │   ├── auth.py        # Local authentication
│   │   │   ├── auth_microsoft.py  # OAuth authentication
│   │   │   ├── user.py        # User management
│   │   │   └── sessions.py   # Session management
│   │   ├── services/          # Business logic
│   │   │   ├── rag_service.py      # RAG orchestration
│   │   │   ├── auth_service.py    # Authentication logic
│   │   │   └── chat_history_service.py  # Chat management
│   │   ├── models/            # SQLModel database models
│   │   │   ├── user.py
│   │   │   └── chat.py
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── selectors/         # Database query functions
│   │   └── dependencies/      # FastAPI dependencies
│   │       ├── auth.py        # Authentication dependencies
│   │       ├── clients.py     # Service client initialization
│   │       └── rate_limit.py  # Rate limiting
│   ├── clients/               # External service clients
│   │   ├── llm.py            # LLM client (xAI)
│   │   ├── embedding_client.py  # Embedding generation
│   │   ├── qdrant.py         # Vector database client
│   │   ├── redis.py          # Redis client
│   │   └── postgres.py       # Database connection
│   ├── chunkers/             # Document processing
│   │   └── ingestion.py     # Document ingestion pipeline
│   ├── scrapers/             # Web scraping utilities
│   └── core/                 # Core configuration
│       └── settings.py       # Environment settings
├── alembic/                  # Database migrations
├── emu_rag_data/             # Source documents (markdown)
├── requirements-prod.txt     # Production dependencies
├── requirements-dev.txt     # Development dependencies
└── Dockerfile                # Container configuration
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Qdrant instance (cloud or local)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd emu-rag
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Configure environment variables**
   Create a `.env` file:
   ```env
   ENV=development
   DATABASE_URL=postgresql://user:password@localhost/dbname
   REDIS_URL=redis://localhost:6379
   QDRANT_URL=https://your-qdrant-instance
   QDRANT_API_KEY=your-api-key
   XAI_API_KEY=your-xai-api-key
   SECRET_KEY=your-secret-key
   ALGORITHM=HS256
   MICROSOFT_CLIENT_ID=your-client-id
   MICROSOFT_CLIENT_SECRET=your-client-secret
   MICROSOFT_TENANT_ID=your-tenant-id
   API_BASE_URL=http://localhost:8000
   ```

4. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

5. **Ingest documents** (first time setup)
   ```bash
   python -m src.chunkers.ingestion
   ```

6. **Start the development server**
   ```bash
   uvicorn src.api.main:app --reload --port 8000
   ```

### Development

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🚢 Deployment

### HuggingFace Spaces

This project is configured for deployment on HuggingFace Spaces using Docker. The configuration is defined in the YAML frontmatter at the top of this README.

### Environment Variables

Set the following secrets in HuggingFace Spaces:
- `DATABASE_URL`
- `REDIS_URL`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `XAI_API_KEY`
- `SECRET_KEY`
- `ALGORITHM`
- `MICROSOFT_CLIENT_ID`
- `MICROSOFT_CLIENT_SECRET`
- `MICROSOFT_TENANT_ID`
- `API_BASE_URL`

### Docker Build

```bash
docker build -t emu-rag .
docker run -p 7860:7860 --env-file .env emu-rag
```

## 🔒 Security Features

- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: Bcrypt password hashing
- **Rate Limiting**: Per-user and per-IP rate limits
- **Token Blacklisting**: Secure logout mechanism
- **Input Validation**: Pydantic schema validation
- **SQL Injection Protection**: SQLModel ORM protection

## 📈 Performance Optimizations

- **Redis Caching**: Fast access to chat history
- **Async Architecture**: Non-blocking I/O operations
- **Connection Pooling**: Efficient database connections
- **Vector Indexing**: Optimized similarity search
- **Batch Processing**: Efficient document ingestion

## 🤝 Contributing

For questions or contributions, please contact the maintainer.



