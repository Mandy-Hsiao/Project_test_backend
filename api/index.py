import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel


from rag.rag_answer import get_rag_answer

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

print("BASE_DIR =", BASE_DIR)
print("ENV_PATH =", ENV_PATH)
print("ENV EXISTS =", ENV_PATH.exists())

load_dotenv(dotenv_path=ENV_PATH, override=True)


# =========================================================
# 1. FastAPI
# =========================================================

app = FastAPI(
    title="SOP AI API",
    description="Gemini API 測試版本",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)







# =========================================================
# 4. Request Model
# =========================================================

class QuestionRequest(BaseModel):
    question: str





# =========================================================
# 6. 首頁
# =========================================================

@app.get("/api")
def home():
    return {
        "message": "SOP AI API is running"
    }


# =========================================================
# 7. Chat API
# =========================================================

@app.post("/api/chat")
def chat(data: QuestionRequest):

    result = get_rag_answer(data.question)

    return result


@app.get("/api/test")
def test():
    return {
        "status": "ok",
        "message": "Vercel FastAPI routing works"
    }

@app.get("/api/test1")
def test1():
    return {
        "status": "ok",
        "message": "Vercel FastAPI routing works"
    }