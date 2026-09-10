import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai

from rag.rag_answer_simple import get_rag_answer

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
# 2. Gemini API Key
# =========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("GEMINI KEY FOUND =", bool(GEMINI_API_KEY))

if not GEMINI_API_KEY:
    raise RuntimeError(
        f"找不到 GEMINI_API_KEY，目前尋找位置：{ENV_PATH}"
    )


# =========================================================
# 3. Gemini Client
# =========================================================

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# 4. Request Model
# =========================================================

class QuestionRequest(BaseModel):
    question: str


# =========================================================
# 5. Gemini
# =========================================================

def ask_gemini(question: str) -> str:

    question = question.strip()

    if not question:
        return "請輸入問題。"

    prompt = f"""
你是兆豐證券資訊部 SOP AI 助教。

目前這是系統測試版本，尚未串接 SOP 資料庫。

請依照一般資訊協助回答使用者問題。

規則：

1. 使用繁體中文。
2. 回答清楚、簡潔、正式。
3. 如果問題資訊不足，請說明需要哪些資訊。
4. 不要假裝已經查詢 SOP 或公司內部資料。

【使用者問題】

{question}

請直接回答。
""".strip()

    try:

        interaction = gemini_client.interactions.create(
            model="gemini-3.6-flash",
            input=prompt
        )

        if not interaction.output_text:
            return "Gemini 未回傳有效回答。"

        return interaction.output_text.strip()

    except Exception as exc:

        print("Gemini API Error:", exc)

        return f"Gemini API 呼叫失敗：{exc}"
    
    
    
app = FastAPI(
    title="SOP AI API",
    version="1.0.0"
)

class QuestionRequest(BaseModel):
    question: str

@app.get("/")
def root():
    return {
        "message": "SOP AI Backend is running"
    }

@app.post("api/chat")
def chat(data: QuestionRequest):
    return get_rag_answer(data.question)