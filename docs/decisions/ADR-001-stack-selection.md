# ADR-001: Initial Technology Stack Selection

## Status

Accepted

## Context

The project needs a beginner-friendly but production-oriented stack for building a deployable Compliance RAG System.

The developer is comfortable with Python and does not currently want to use Next.js, TypeScript, Tailwind, OpenAI APIs, or advanced infrastructure tools.

## Decision

The initial stack will be:

- Frontend: Streamlit
- Backend API: FastAPI
- LLM and embeddings: Google Gemini API
- Vector database: Pinecone
- Authentication, relational database, and file storage: Supabase
- Deployment: Render
- Language: Python
- Version control: Git and GitHub

## Rationale

### Streamlit

Allows a usable frontend to be built with Python without requiring a separate JavaScript framework.

### FastAPI

Provides typed API contracts, automatic API documentation, validation through Pydantic, and a clean backend structure.

### Gemini API

Matches the available API access and provides both LLM generation and embeddings.

### Pinecone

Provides managed vector search, metadata filtering, and a simple starting point for document retrieval.

### Supabase

Provides authentication, Postgres, and file storage in one platform.

### Render

Provides a beginner-friendly deployment path for FastAPI, Streamlit, and background workers.

## Consequences

### Positive

- Faster development with a Python-first stack.
- Clear separation between frontend and backend.
- Practical managed services for a public deployment.
- Good fit for a portfolio project.

### Negative

- Free-tier limits may affect deployment behavior.
- Streamlit provides less UI flexibility than React.
- Multiple cloud services increase configuration work.
- Pinecone and Gemini usage may require quota/cost management.

## Future Reconsideration

This decision may be revisited if:

- The product needs a more advanced frontend.
- Pinecone becomes too expensive or restrictive.
- Supabase pgvector becomes a better fit.
- Background ingestion requires a durable queue.
- The project grows into a multi-organization SaaS product.