import os
import re
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

     
from rag.rag_answer import get_rag_answer

from rag.gemini_key_manager import create_gemini_interaction




from fastapi.middleware.cors import CORSMiddleware







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


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://project-test-tau-self.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ③ 定義請求格式
class ChatRequest(BaseModel):
    question: str





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



# =========================================================
# 7.1 對話標題摘要（給左側討論串標題用）
# =========================================================

class TitleMessage(BaseModel):
    role: str
    content: str


class TitleRequest(BaseModel):
    messages: list[TitleMessage]


def _clean_for_title(text: str, limit: int) -> str:
    """移除【來源】標記與 Markdown 符號，並截短，避免浪費 token。"""
    text = re.sub(r"[（(]?【來源】[^）)\n]*[）)]?", "", text or "")
    text = re.sub(r"[#*`>]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _clean_title(raw: str, max_len: int = 20) -> str:
    title = (raw or "").strip().splitlines()[0] if (raw or "").strip() else ""
    title = re.sub(r"^(標題|對話標題|Title)\s*[:：]\s*", "", title)
    title = title.strip(" \t\"'「」『』《》。.，,！!？?")
    return title[:max_len]


@app.post("/api/title")
def make_title(data: TitleRequest):
    # 只取最近 12 則，避免對話太長
    msgs = data.messages[-12:]

    lines = []
    for m in msgs:
        is_user = m.role == "user"
        text = _clean_for_title(m.content, 200 if is_user else 300)
        if text:
            lines.append(f"{'使用者' if is_user else 'AI'}：{text}")

    first_user = next(
        (_clean_for_title(m.content, 15) for m in data.messages if m.role == "user"),
        "",
    )
    fallback = first_user or "新對話"

    if not lines:
        return {"title": fallback}

    conversation = "\n".join(lines)
    prompt = f"""
請閱讀下方「使用者」與「AI」的對話，用繁體中文整理出整段對話的大意，並濃縮成一個對話標題。

規則：
1. 標題要概括整段對話在討論什麼，不是只複製第一個問題。
2. 長度 8 到 15 個字，不要超過 20 字。
3. 不要加標點符號、引號、「標題：」這類前綴。
4. 只輸出標題本身，不要任何解釋。

【對話內容】
{conversation}

標題：
""".strip()

    try:
        interaction = create_gemini_interaction(
            prompt=prompt,
            model="gemini-3.6-flash",
            thinking_level="low",
            max_output_tokens=1024,
            read_timeout=20,
        )
        title = _clean_title(interaction.output_text)
    except Exception as exc:
        print("Gemini Title Error:", exc)
        title = ""

    return {"title": title or fallback}


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