import os
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone


# ============================================================
# 1. 讀取環境變數
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

load_dotenv(
    ENV_PATH
)


# ============================================================
# 2. Pinecone 設定
# ============================================================

PINECONE_API_KEY = os.getenv(
    "PINECONE_API_KEY"
)

PINECONE_INDEX_NAME = os.getenv(
    "PINECONE_INDEX_NAME"
)

if not PINECONE_API_KEY:
    raise ValueError(
        "找不到 PINECONE_API_KEY"
    )

if not PINECONE_INDEX_NAME:
    raise ValueError(
        "找不到 PINECONE_INDEX_NAME"
    )


# ============================================================
# 3. 連線 Pinecone
# ============================================================

pc = Pinecone(
    api_key=PINECONE_API_KEY
)

index = pc.Index(
    PINECONE_INDEX_NAME
)


# ============================================================
# 4. 清除指定 namespace
# ============================================================

NAMESPACE = "sop-child"

print(
    f"準備清除 namespace：{NAMESPACE}"
)

index.delete(
    delete_all=True,
    namespace=NAMESPACE
)

print(
    f"已清除 namespace：{NAMESPACE}"
)