import os
import time

from pinecone import Pinecone, ServerlessSpec


INDEX_NAME = os.environ["PINECONE_INDEX_NAME"]
DIMENSION = int(os.environ.get("GEMINI_EMBEDDING_DIMENSION", "768"))

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

if not pc.has_index(INDEX_NAME):
    pc.create_index(
        name=INDEX_NAME,
        dimension=DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1",
        ),
    )
    print(f"Creating Pinecone index: {INDEX_NAME}")

    while not pc.describe_index(INDEX_NAME).status["ready"]:
        time.sleep(1)

print(pc.describe_index(INDEX_NAME))