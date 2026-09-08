import os 
from pathlib import Path 
 
from dotenv import load_dotenv 
from openai import OpenAI 
from pinecone import Pinecone 
from google import genai 
 
 
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
 
# Gemini 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
 
 
# ========================================================= 
# 3. Azure OpenAI Client 
#    只用於 Embedding 
# ========================================================= 
 
azure_client = OpenAI( 
    api_key=AZURE_OPENAI_API_KEY, 
    base_url=f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/", 
) 
 
 
# ========================================================= 
# 4. Gemini Client 
# ========================================================= 
 
gemini_client = genai.Client( 
    api_key=GEMINI_API_KEY 
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

def ask_gemini_llm(question: str, context: str) -> str:

    prompt = f"""
你是兆豐證券資訊部 SOP AI 助教。

請嚴格根據提供的 SOP 內容回答使用者問題。

規則：

1. 不得自行補充 SOP 中不存在的資訊。
2. 如果 SOP 中沒有足夠資訊回答，請回答：
   「目前 SOP 文件中沒有相關資訊。」
3. 使用繁體中文。
4. 回答清楚、簡潔、正式。
5. 完整保留 SOP 中的重要資訊。

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
            vector=query_embedding, 
            top_k=3, 
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
    # Step 5：Context → Gemini 
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
 
    import sys 
 
    if len(sys.argv) < 2: 
 
        print("請輸入問題。") 
 
    else: 
 
        question = " ".join(sys.argv[1:]) 
 
        print("\n問題：", question) 
        print("\n回答：") 
        print(get_rag_answer(question))