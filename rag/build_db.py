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
    / "parent_child_chunks.json"
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
# 7. 將 Child 轉成 Pinecone Vector
# ============================================================

def child_to_vector(child):

    text = child["text"]

    embedding = create_embedding(
        text
    )

    metadata = {

        "child_id":
            child["child_id"],

        "parent_id":
            child["parent_id"],

        "file_name":
            child["file_name"],

        "storage_path":
            child["storage_path"],

        "page":
            child["page"],

        "section_title":
            child.get(
                "section_title",
                ""
            ),

        "content_type":
            child.get(
                "content_type",
                "text"
            ),

        "text":
            text
    }

    vector = {

        "id":
            child["child_id"],

        "values":
            embedding,

        "metadata":
            metadata
    }

    return vector


# ============================================================
# 8. Upload
# ============================================================

def upload_all():

    data = load_chunks()

    vectors = []

    total_children = sum(
        len(item["children"])
        for item in data
    )

    print(
        f"找到 {total_children} 個 Child Chunk"
    )

    processed = 0

    for item in data:

        children = item[
            "children"
        ]

        for child in children:

            processed += 1

            print(
                f"[{processed}/{total_children}] "
                f"Embedding："
                f"{child['child_id']}"
            )

            vector = (
                child_to_vector(
                    child
                )
            )

            vectors.append(
                vector
            )

            # 每 50 筆送一次 Pinecone
            if len(vectors) >= 50:

                index.upsert(
                    vectors=vectors,
                    namespace="sop-child"
                )

                print(
                    f"已上傳 {len(vectors)} 筆"
                )

                vectors = []

    # 最後不足 50 筆
    if vectors:

        index.upsert(
            vectors=vectors,
            namespace="sop-child"
        )

        print(
            f"最後上傳 {len(vectors)} 筆"
        )

    print(
        "\nPinecone 上傳完成"
    )


# ============================================================
# 9. Main
# ============================================================

if __name__ == "__main__":

    upload_all()
