# System Architecture

## Overview

The Compliance RAG System uses a frontend, backend API, relational database, file storage, vector database, and LLM service.

```text
Streamlit Frontend
        |
        | HTTPS API requests
        v
FastAPI Backend
        |
        +--------------------+
        |                    |
        v                    v
Supabase                 Pinecone
- Authentication         - Document chunk vectors
- Postgres database      - Metadata filtering
- Private file storage   - User/tenant isolation
        |
        v
Gemini API
- Embeddings
- Grounded answer generation