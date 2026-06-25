# Compliance RAG System

A production-oriented Retrieval-Augmented Generation (RAG) system for securely querying compliance documents with citation-backed answers.

## Problem

Compliance, audit, and security teams often need to search across policies, regulations, audit evidence, internal controls, and contracts.

Manual document search is slow, difficult to verify, and can lead to missed information.

## Solution

Users upload compliance documents and ask questions in natural language.

The system retrieves relevant evidence from the uploaded documents and generates grounded answers with page-level citations where available.

## Target Users

- Compliance analysts
- Internal auditors
- Governance, Risk, and Compliance (GRC) teams
- Security teams
- Small and mid-sized companies preparing for audits

## Core Features

- Secure user authentication
- PDF document upload and management
- Background document ingestion
- Page-aware document chunking
- Semantic retrieval using embeddings
- Metadata filtering
- Citation-backed answers
- "I don't know based on the documents" behavior
- User-level document isolation
- Logging, testing, deployment, and documentation

## Technology Stack

- Frontend: Streamlit
- Backend API: FastAPI
- LLM and embeddings: Google Gemini API
- Vector database: Pinecone
- Authentication, database, and storage: Supabase
- Deployment: Render
- Language: Python

## Project Status

Planning and local development setup.

## Documentation

- [Architecture](docs/architecture.md)
- [Product Requirements](docs/product-requirements.md)
- [Risks and Assumptions](docs/risks-and-assumptions.md)
- [Architecture Decision Records](docs/decisions/)