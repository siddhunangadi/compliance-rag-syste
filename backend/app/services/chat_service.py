from typing import List, Optional

from google import genai

from app.core.config import settings
from app.schemas.chat import Citation, ChatResponse
from app.prompts.compliance_rag import build_rag_prompt
from app.services.retrieval_service import RetrievalService


MIN_RETRIEVAL_SCORE = 0.55


class ChatService:
    def __init__(self):
        self.retrieval_service = RetrievalService()

        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )

    async def ask(
        self,
        question: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> ChatResponse:

        chunks = await self.retrieval_service.retrieve(
            question=question,
            user_id=user_id,
            document_ids=document_ids,
            top_k=top_k,
        )

        if not chunks:
            return ChatResponse(
                answer="I could not find enough evidence in the uploaded documents to answer this question.",
                citations=[],
                retrieval_score=0.0,
                grounded=False,
            )

        best_score = chunks[0]["score"]

        if best_score < MIN_RETRIEVAL_SCORE:
            return ChatResponse(
                answer="I could not find enough evidence in the uploaded documents to answer this question.",
                citations=[],
                retrieval_score=best_score,
                grounded=False,
            )

        context_parts = []

        for index, chunk in enumerate(chunks, start=1):
            context_parts.append(
                f"""
[Source {index}]
Document: {chunk["document_name"]}
Chunk ID: {chunk["chunk_id"]}
Content:
{chunk["text"]}
"""
            )

        context = "\n\n".join(context_parts)

        prompt = build_rag_prompt(
            question=question,
            context=context,
        )

        response = self.client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=prompt,
        )

        answer = response.text.strip()

        citations: List[Citation] = []

        for chunk in chunks:
            excerpt = chunk["text"][:350].strip()

            citations.append(
                Citation(
                    document_id=chunk["document_id"],
                    document_name=chunk["document_name"],
                    chunk_id=chunk["chunk_id"],
                    page_number=chunk.get("page_number"),
                    excerpt=excerpt,
                    score=chunk["score"],
                )
            )

        return ChatResponse(
            answer=answer,
            citations=citations,
            retrieval_score=best_score,
            grounded=True,
        )