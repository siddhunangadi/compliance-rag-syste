import os

from google import genai
from google.genai import types


client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

response = client.models.embed_content(
    model=os.environ["GEMINI_EMBEDDING_MODEL"],
    contents="Only authorized employees may access customer data.",
    config=types.EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=int(
            os.environ.get("GEMINI_EMBEDDING_DIMENSION", "768")
        ),
    ),
)

embedding = response.embeddings[0].values

print(
    {
        "model": os.environ["GEMINI_EMBEDDING_MODEL"],
        "embedding_dimension": len(embedding),
        "first_5_values": embedding[:5],
    }
)