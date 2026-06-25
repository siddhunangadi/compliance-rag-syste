from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.documents import router as documents_router
from app.api.routes.chat import router as chat_router


app = FastAPI(
    title="Compliance RAG System API",
    description="Production-ready compliance document retrieval and question-answering API.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Compliance RAG System API is running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "compliance-rag-api",
    }


# Document upload, listing, deletion, and ingestion endpoints
app.include_router(
    documents_router,
    prefix="/api/v1",
)

# Compliance RAG question-answering endpoint
app.include_router(
    chat_router,
    prefix="/api/v1",
)