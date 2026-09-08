from pinecone import Pinecone
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX")
NAMESPACE = os.getenv("PINECONE_NAMESPACE")

pc = Pinecone(
    api_key=PINECONE_API_KEY
)

index = pc.Index("sop-ai")


question = "VPN不能登入怎麼辦？"


result = index.search(
    namespace="sop",

    query={
        "inputs": {
            "text": question
        },

        "top_k": 3
    }
)

print("問題：", question)

print("\n找到的資料：")

for hit in result.result.hits:

    print("----------------")

    print("Score：", hit.score)

    print("Text：")
    print(hit.fields["text"])
