import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from fastapi import FastAPI
from pydantic import BaseModel


# =========================================================
# 1. 載入 .env
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# =========================================================
# 2. 讀取 Gemini API Key
# =========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# =========================================================
# 3. Gemini Client
# =========================================================

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# 4. FastAPI
# =========================================================

app = FastAPI()


# =========================================================
# 5. 接收前端傳來的 JSON
# =========================================================

class QuestionRequest(BaseModel):
    question: str


# =========================================================
# 6. 直接詢問 Gemini
# =========================================================

def get_rag_answer(question: str) -> str:

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


# =========================================================
# 7. FastAPI Chat API
# =========================================================

@app.post("/chat")
def chat(data: QuestionRequest):

    answer = get_rag_answer(data.question)

    return {
        "answer": answer
    }


# =========================================================
# 8. 測試首頁
# =========================================================

@app.get("/")
def home():

    return {
        "message": "SOP AI API is running"
    }