import os 
from pathlib import Path 
 
from dotenv import load_dotenv 
from openai import OpenAI 
from pinecone import Pinecone

from rag.gemini_key_manager import create_gemini_interaction
 
 
 
# ========================================================= 
# 1. 載入 .env 
# ========================================================= 
 
BASE_DIR = Path(__file__).resolve().parent.parent 
load_dotenv(BASE_DIR / ".env") 
 
 
# ========================================================= 
# 2. 讀取環境變數 
# ========================================================= 
 
# Pinecone 
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY") 
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME") 
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE") 
 
# Azure OpenAI 
# 目前只保留給 Embedding 使用 
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") 
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY") 
 
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv( 
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT" 
) 
 


 
 
# ========================================================= 
# 3. Azure OpenAI Client 
#    只用於 Embedding 
# ========================================================= 
 
azure_client = OpenAI( 
    api_key=AZURE_OPENAI_API_KEY, 
    base_url=f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/", 
) 
 

 
# ========================================================= 
# 5. Pinecone Client 
# ========================================================= 
 
pc = Pinecone( 
    api_key=PINECONE_API_KEY 
) 
 
index = pc.Index(PINECONE_INDEX_NAME) 
 
 
# ========================================================= 
# 6. Azure Embedding 
# ========================================================= 
 
def get_embedding(text: str): 
 
    response = azure_client.embeddings.create( 
        model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT, 
        input=text 
    ) 
 
    return response.data[0].embedding 
 
 

# =========================================================
# 7. Gemini LLM
# =========================================================

def ask_gemini_llm(
    question: str,
    context: str
) -> str:

    prompt = f"""
你是兆豐證券資訊部 SOP AI 助教。

你會收到多段從公司SOP資料庫中檢索出來的文件片段，以及使用者的問題。

請依照以下步驟處理：
1. 逐一檢視每段檢索到的內容，判斷是否包含與問題「直接相關」或「可合理推導」的資訊。
   - 直接相關：文件明確提到問題所問的流程、規定、數值、條件。
   - 可合理推導：文件雖未逐字對應問題措辞，但描述的情境、流程步驟、
     適用範圍等可以合理回答問題。
2. 只有在「所有檢索片段都與問題完全無關」的情況下，才回答：
   「目前資料庫中查無與此問題直接相關的SOP資訊，建議聯繫OO部門確認。」
3. 若片段中僅有「部分」相關資訊，仍應根據可用內容回答，並註明：
   「以下回答依據現有SOP片段整理，若涉及尚未提及的細節，建議進一步確認。」
4. 禁止在檢索片段中含有相關關鍵字或敘述時，直接回覆「沒有相關資訊」。

回答時請標示資訊確定程度：
- 【明確依據】：SOP文件中有直接對應的敘述
- 【推論整理】：根據多段SOP內容綜合判斷
- 【建議確認】：資料庫中僅有部分相關資訊，需人工複核的部分

不要因為某部分不確定，就整體判定為「查無相關資料」。

========================

【SOP 內容】

{context}

========================

【使用者問題】

{question}

========================

請直接回答。
""".strip()

    try:

        interaction = create_gemini_interaction(
            prompt=prompt,
            model="gemini-3.6-flash"
        )

        if not interaction.output_text:
                    return {
                        "answer": "Gemini 未回傳有效回答。",
                        "input_tokens": 0,
                        "thinking_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0
                    }
        
        usage = interaction.usage

        return {
            "answer": interaction.output_text.strip(),

            "input_tokens":
                usage.total_input_tokens
                if usage else 0,

            "thinking_tokens":
                usage.thinking_tokens
                if usage else 0,

            "output_tokens":
                usage.total_output_tokens
                if usage else 0,

            "total_tokens":
                usage.total_tokens
                if usage else 0
        }

    except Exception as exc:

        print("Gemini API Error:", exc)

        return {
        "answer":
            f"Gemini API 呼叫失敗：{exc}",

        "input_tokens": 0,
        "thinking_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0
    }
 
 
# ========================================================= 
# 8. RAG 主程式 
# ========================================================= 
 
def get_rag_answer(question: str) -> str: 
 
    question = question.strip() 
 
    if not question: 
        return "請輸入問題。" 
 
 
    # ----------------------------------------------------- 
    # Step 1：問題 → Azure Embedding 
    # ----------------------------------------------------- 
 
    try: 
 
        query_embedding = get_embedding(question) 
 
    except Exception as exc: 
 
        print("Embedding Error:", exc) 
 
        return f"Embedding 產生失敗：{exc}" 
 
 
    # ----------------------------------------------------- 
    # Step 2：Pinecone 語意檢索 
    # ----------------------------------------------------- 
 
    try: 
 
        results = index.query( 
            namespace=PINECONE_NAMESPACE,
            #使用者問題的向量交給 Pinecone，請 Pinecone 找出與它最接近的向量。 
            vector=query_embedding, 
            top_k=6, 
            include_metadata=True 
        ) 
 
    except Exception as exc: 
 
        print("Pinecone Error:", exc) 
 
        return f"Pinecone 搜尋失敗：{exc}" 
 
 
    # ----------------------------------------------------- 
    # Step 3：取得 Pinecone 文件 
    # ----------------------------------------------------- 
 
    documents = [] 
 
    for match in results.matches: 
 
        metadata = match.metadata or {} 
 
        # 相容兩種 metadata 欄位名稱 
        content = ( 
            metadata.get("content") 
            or metadata.get("text") 
            or "" 
        ) 
 
        if content: 
            documents.append(content) 
 
 
    if not documents: 
 
        return "目前 SOP 文件中沒有相關資訊。" 
 
 
    # ----------------------------------------------------- 
    # Step 4：建立 Context 
    # ----------------------------------------------------- 
 
    context = "\n\n".join(documents) 
 
 
    # Debug：檢查 Pinecone 到底抓到什麼 
    print("\n========== Pinecone 檢索結果 ==========") 
 
    for i, document in enumerate(documents, start=1): 
        print(f"\n--- 文件 {i} ---") 
        print(document) 
 
    print("\n========================================\n") 
 
 
    # ----------------------------------------------------- 
    # Step 5：Context → Gemini (回傳答案給LLM)
    # ----------------------------------------------------- 
 
    answer = ask_gemini_llm( 
        question=question, 
        context=context 
    ) 
 
    return answer 
 
 
# ========================================================= 
# 9. 本機測試 
# ========================================================= 
 
if __name__ == "__main__":

    question = input("請輸入問題：")

    if not question.strip():

        print("問題不能為空。")

    else:

        print("\n問題：", question)
        print("\n回答：")
        print(get_rag_answer(question))