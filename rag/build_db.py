import os
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone


# ============================================================
# 1. 路徑 / .env
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

ENV_PATH = (
    BASE_DIR
    / ".env"
)

JSON_PATH = (
    BASE_DIR
    / "output"
    / "semantic_chunks.json"
)

load_dotenv(
    ENV_PATH
)


# ============================================================
# 2. 環境變數
# ============================================================

PINECONE_API_KEY = os.getenv(
    "PINECONE_API_KEY"
)

PINECONE_INDEX_NAME = os.getenv(
    "PINECONE_INDEX_NAME"
)

AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT"
)

AZURE_OPENAI_API_KEY = os.getenv(
    "AZURE_OPENAI_API_KEY"
)

AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
)


if not PINECONE_API_KEY:
    raise ValueError(
        "找不到 PINECONE_API_KEY"
    )

if not PINECONE_INDEX_NAME:
    raise ValueError(
        "找不到 PINECONE_INDEX_NAME"
    )

if not AZURE_OPENAI_ENDPOINT:
    raise ValueError(
        "找不到 AZURE_OPENAI_ENDPOINT"
    )

if not AZURE_OPENAI_API_KEY:
    raise ValueError(
        "找不到 AZURE_OPENAI_API_KEY"
    )

if not AZURE_OPENAI_EMBEDDING_DEPLOYMENT:
    raise ValueError(
        "找不到 AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )


# ============================================================
# 3. Azure OpenAI Client
# ============================================================

embedding_client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=(
        AZURE_OPENAI_ENDPOINT.rstrip("/")
        + "/openai/v1/"
    )
)


# ============================================================
# 4. Pinecone Client
# ============================================================

pc = Pinecone(
    api_key=PINECONE_API_KEY
)

index = pc.Index(
    PINECONE_INDEX_NAME
)


# ============================================================
# 5. 讀 JSON
# ============================================================

def load_chunks():

    if not JSON_PATH.exists():

        raise FileNotFoundError(
            f"找不到：{JSON_PATH}"
        )

    with open(
        JSON_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    return data


# ============================================================
# 6. Azure OpenAI Embedding
# ============================================================

def create_embedding(text):

    response = (
        embedding_client
        .embeddings
        .create(
            model=(
                AZURE_OPENAI_EMBEDDING_DEPLOYMENT
            ),
            input=text
        )
    )

    return (
        response
        .data[0]
        .embedding
    )


# ============================================================
# 7. 將 Semantic Chunk 轉成 Pinecone Vector
# ============================================================

def chunk_to_vector(chunk):
    text = chunk["text"]
    embedding = create_embedding(text)
    metadata = {
        "chunk_id": chunk["chunk_id"],
        "file_name": chunk["file_name"],
        "storage_path": chunk["storage_path"],
        "page": chunk["page"],
        "section_title": chunk.get("section_title", ""),
        "content_type": chunk.get("content_type", "text"),
        "text": text,
    }
    return {"id": chunk["chunk_id"], "values": embedding, "metadata": metadata}


# ============================================================
# 8. Upload
# ============================================================

def upload_all():
    data = load_chunks()
    PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE")
    if not PINECONE_NAMESPACE:
        raise ValueError("請設定 PINECONE_NAMESPACE，並與 rag_answer.py 使用相同值")
    if not isinstance(data, list) or any(
        not isinstance(item, dict) or not item.get("chunk_id") or
        not isinstance(item.get("text"), str) or not item["text"].strip() or
        not all(key in item for key in ("file_name", "storage_path", "page"))
        for item in data
    ):
        raise ValueError("JSON 必須為單層 Semantic Chunk 陣列，請重新執行 chunk_PDF.py")
    print(f"找到 {len(data)} 個 Semantic Chunk")
    vectors = []
    for processed, item in enumerate(data, start=1):
        print(f"[{processed}/{len(data)}] Embedding：{item['chunk_id']}")
        vectors.append(chunk_to_vector(item))
        if len(vectors) >= 50:
            index.upsert(vectors=vectors, namespace=PINECONE_NAMESPACE)
            print(f"已上傳 {len(vectors)} 筆")
            vectors = []
    if vectors:
        index.upsert(vectors=vectors, namespace=PINECONE_NAMESPACE)
        print(f"最後上傳 {len(vectors)} 筆")
    print("\nPinecone 上傳完成")


# ============================================================
# 9. Main
# ============================================================

if __name__ == "__main__":

    upload_all()
