import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

     
from rag.rag_answer import get_rag_answer

from rag.gemini_key_manager import create_gemini_interaction


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



#Test

@app.get("/api/gemini-test")
def gemini_test():

    try:

        interaction = create_gemini_interaction(
            prompt="請只回答：Gemini 測試成功",
            model="gemini-3.6-flash"
        )

        return {
            "status": "ok",
            "answer": interaction.output_text
        }

    except Exception as exc:

        return {
            "status": "error",
            "error": str(exc)
        }



# =========================================================
# 4. Request Model
# =========================================================

class QuestionRequest(BaseModel):
    question: str





# =========================================================
# 5.1 主題相關性判斷（judge專用）
# =========================================================

# 這裡描述目前 chatbot 的主題範圍，之後要換主題只要改這個字串即可
TOPIC_DESCRIPTION = """
證券業資訊部相關的 SOP（標準作業流程）與員工常見問題，主要服務對象是新進人員與部門內同仁，
目的是降低新人學習成本、減少重複性問題的人工回覆。範圍涵蓋：

1. 資訊系統操作與帳號權限：系統登入、帳號申請、權限開通/變更、密碼重置、系統故障通報。
2. 內部作業與資料處理流程：報表產出、資料上傳下載、批次作業、異常處理與通報流程。
3. 資安與合規相關作業規範：資料存取規範、對外傳輸規範、稽核相關作業。
4. 全公司通用的行政與人資類問題：請假申請、差勤/加班申報、差旅報帳、設備/耗材申請、教育訓練報名。
5. 新進人員上手相關問題：辦公環境與設備介紹、常用系統與工具介紹、聯絡窗口與部門分工、教育訓練排程。

只要問題落在上述任一類別，或是新人在熟悉公司作業流程過程中合理會問的問題，都算相關；
與工作及公司作業流程完全無關的閒聊、時事、其他產業知識等才算不相關。
""".strip()

# 判斷不相關時要回傳給使用者的訊息
OFF_TOPIC_MESSAGE = "很抱歉，這個問題似乎與本系統的主題（SOP 流程相關問題）無關，請重新提出與 SOP 相關的問題。"


def is_question_on_topic(question: str) -> bool:
    """
    使用 Gemini 判斷使用者問題是否與指定主題相關。
    回傳 True 表示相關（放行），False 表示不相關（擋住）。
    """

    question = question.strip()

    if not question:
        # 空問題視為不相關，直接擋住
        return False

    classify_prompt = f"""
你是一個主題分類器。

請判斷下方的「使用者問題」是否與以下主題相關：

【主題】
{TOPIC_DESCRIPTION}

規則：
1. 只要問題內容與上述主題有一定程度的關聯（即使不是非常明確），就算相關。
2. 與上述主題完全無關的閒聊、通用知識問題、其他公司或其他系統的問題，視為不相關。
3. 只能回答一個字："是" 或 "否"，不要有任何其他文字、標點或解釋。

【使用者問題】
{question}

請只回答「是」或「否」：
""".strip()

    try:
        interaction = create_gemini_interaction(
            prompt=classify_prompt,
            model="gemini-3.6-flash"
        )

        answer = (interaction.output_text or "").strip()
        return "是" in answer and "否" not in answer

    except Exception as exc:

        print("Gemini Topic Classification Error:", exc)
        return False


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

@app.post("/api/judge")
def test1(data: QuestionRequest):

    question = data.question.strip()

    if not question:
        return {
            "status": "blocked",
            "message": "請輸入問題。"
        }

    on_topic = is_question_on_topic(question)

    if not on_topic:
        return {
            "status": "blocked",
            "message": OFF_TOPIC_MESSAGE
        }

    # 相關就照原本的邏輯繼續走 RAG 回答
    result = get_rag_answer(question)

    return {
        "status": "ok",
        "result": result
    }