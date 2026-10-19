import os
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

try:
    from .document_metadata import enrich_chunks
except ImportError:  # python rag/build_db.py
    from document_metadata import enrich_chunks


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

    return enrich_chunks(data)


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
    """Metadata 記錄文件身分；向量文字也帶上文件標題以改善召回率。"""
    text = chunk["text"]
    title = chunk["document_title"]
    content_for_embedding = (
        f"文件標題：{title}\n"
        f"文件類型：{chunk['document_type']}\n"
        f"章節：{chunk.get('section_title') or ''}\n"
        f"內容：{text}"
    )
    embedding = create_embedding(content_for_embedding)
    metadata = {
        "schema_version": "document_v2",
        "chunk_id": chunk["chunk_id"],
        "file_name": chunk["file_name"],
        "storage_path": chunk["storage_path"],
        "document_id": chunk["document_id"],
        "document_title": title,
        "document_type": chunk["document_type"],
        "chunk_seq": chunk["chunk_seq"],
        "document_chunk_count": chunk["document_chunk_count"],
        "page": chunk["page"],
        "section_title": chunk.get("section_title") or "",
        "content_type": chunk.get("content_type", "text"),
        "text": text,  # 原文供引用，不在前面添加 Metadata
    }
    # Pinecone Metadata 不接受 None，首尾沒有相鄰片段時省略欄位。
    if chunk.get("prev_chunk_id"):
        metadata["prev_chunk_id"] = chunk["prev_chunk_id"]
    if chunk.get("next_chunk_id"):
        metadata["next_chunk_id"] = chunk["next_chunk_id"]
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
    print(f"找到 {len(data)} 個 Semantic Chunk（{len({c['document_id'] for c in data})} 份文件）")
    print(f"目標 Namespace：{PINECONE_NAMESPACE}（建議使用新 Namespace，避免混入舊版向量）")
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
