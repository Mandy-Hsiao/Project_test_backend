import os
import re
import unicodedata
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

# =========================================================
# 7. Retrieval：候選擴充 + 精確名稱重排
# =========================================================
# 這不是 Pinecone 原生 hybrid search；是向量檢索後的規則重排。
RETRIEVAL_TOP_K = max(6, min(int(os.getenv("RAG_RETRIEVAL_TOP_K", "20")), 100))
CONTEXT_TOP_K = max(1, min(int(os.getenv("RAG_CONTEXT_TOP_K", "5")), 15))

ADDRESS_QUESTION = re.compile(r"地址|住址|位址|在哪裡|在哪|位置|地點|怎麼去|郵遞區號|郵編")
ADDRESS_VALUE = re.compile(r"(?:[\u4e00-\u9fff]{2,3}[縣市])?(?:[\u4e00-\u9fff]{1,5}[區鄉鎮市])?[\u4e00-\u9fff0-9一二三四五六七八九十]+(?:路|街|大道)(?:[\u4e00-\u9fff0-9一二三四五六七八九十]+(?:段|巷|弄))*[0-9０-９一二三四五六七八九十]+號")
ORG_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9（）()·．.\-]{2,45}?(?:分公司|營業處|營業部|辦事處|服務中心|分行|總公司|總部|證券商|門市|據點|機房)")


def normalize(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text or ""))).lower()


def question_entities(question):
    # 把問題詞、泛稱移除，留下完整機構名稱；不要把「哪間分公司」當實體。
    q = re.sub(r"[？?，,。:：\s]", "", question)
    entities = []
    for m in ORG_PATTERN.finditer(q):
        name = m.group(0)
        name = re.sub(r"^(請問|想知道|查詢|告訴我|請提供|請查|我想知道|關於)", "", name)
        name = re.sub(r"^(哪一間|哪間|哪個|哪家|這間|該|某)", "", name)
        if len(name) >= 3 and name not in ("分公司", "總公司", "營業部", "服務中心"):
            entities.append(name)
    return list(dict.fromkeys(entities))


def candidate_text(meta):
    return str(meta.get("text") or meta.get("content") or "").strip()


def rerank_matches(question, matches):
    entities = question_entities(question)
    is_address = bool(ADDRESS_QUESTION.search(question))
    ranked = []
    for match in matches:
        meta = dict(getattr(match, "metadata", None) or {})
        body = candidate_text(meta)
        if not body:
            continue
        # 文件名/標題可能帶有單位名稱；但地址必須來自內文，不可由 metadata 猜測。
        identity = normalize(" ".join((body, str(meta.get("section_title", "")), str(meta.get("file_name", "")))))
        matched = [e for e in entities if normalize(e) in identity]
        score = float(getattr(match, "score", 0) or 0)
        exact_bonus = 3.0 * len(matched)
        address_bonus = 0.2 if is_address and (ADDRESS_VALUE.search(body) or "地址" in body) else 0
        ranked.append({"match": match, "metadata": meta, "text": body,
                       "score": score + exact_bonus + address_bonus,
                       "entity_match": bool(matched), "has_address": bool(ADDRESS_VALUE.search(body))})
    # 地址題如含明確單位名稱，只允許有該名稱的片段進入生成，避免別家地址混入。
    if is_address and entities:
        ranked = [r for r in ranked if r["entity_match"]]
    ranked.sort(key=lambda x: x["score"], reverse=True)
    seen = set()
    unique = []
    for row in ranked:
        key = normalize(row["text"])
        if key not in seen:
            unique.append(row)
            seen.add(key)
        if len(unique) >= CONTEXT_TOP_K:
            break
    return unique, entities, is_address


def response(answer, usage=None):
    return {
        "answer": answer,
        "input_tokens": getattr(usage, "total_input_tokens", 0) if usage else 0,
        "thinking_tokens": getattr(usage, "thinking_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "total_output_tokens", 0) if usage else 0,
        "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
    }


def ask_gemini_llm(question: str, context: str, address_mode=False) -> dict:
    address_rules = """
地址／聯絡資訊特別規則：
- 必須逐字引用 SOP 中同一單位明確對應的完整地址，不能補全、猜測、換算或自行查詢。
- 同頁出現多家單位時，不得把某一家的地址誤配到另一家。
- 若檢索內容只有單位名稱，沒有能確認歸屬的完整地址，明確說無法確認，不得提供近似地址。
- 若多份資料衝突，列出來源及差異並請人工核對，不可擅自挑選。
""" if address_mode else ""
    prompt = f"""你是兆豐證券資訊部 SOP AI 助教。僅使用以下 SOP 片段作答。
回答必須有可追溯的文件依據；不允許以常識或猜測補足未提供的內容。
若資料不足，請明確指出缺少的部分；不得虛構聯絡部門。
請使用繁體中文。引用資料時盡量標示來源檔名與頁碼。
{address_rules}
【檢索文件】
{context}
【問題】
{question}
""".strip()
    try:
        interaction = create_gemini_interaction(prompt=prompt, model="gemini-3.6-flash")
        if not interaction.output_text:
            return response("Gemini 未回傳有效回答。")
        return response(interaction.output_text.strip(), interaction.usage)
    except Exception as exc:
        print("Gemini API Error:", exc)
        return response("Gemini API 呼叫失敗，請稍後再試。")


# =========================================================
# 8. RAG 主程式
# =========================================================
def get_rag_answer(question: str) -> dict:
    question = question.strip()
    if not question:
        return response("請輸入問題。")
    try:
        query_embedding = get_embedding(question)
    except Exception as exc:
        print("Embedding Error:", exc)
        return response("Embedding 產生失敗，請檢查服務設定。")
    try:
        results = index.query(namespace=PINECONE_NAMESPACE,
                              vector=query_embedding,
                              top_k=RETRIEVAL_TOP_K,
                              include_metadata=True)
    except Exception as exc:
        print("Pinecone Error:", exc)
        return response("Pinecone 搜尋失敗，請檢查服務設定。")

    ranked, entities, address_mode = rerank_matches(question, results.matches or [])
    if not ranked:
        if address_mode and entities:
            return response("目前檢索結果無法確認「" + "、".join(entities) + "」的地址，請核對 SOP 原始文件。")
        return response("目前 SOP 文件中沒有足夠資訊回答此問題。")

    # 地址查詢時，如果找不到帶有地址的候選，不要讓 LLM 猜地址。
    if address_mode and not any(r["has_address"] for r in ranked):
        return response("目前檢索片段沒有可確認的完整地址，請核對 SOP 原始文件。")

    blocks = []
    for i, row in enumerate(ranked, 1):
        meta = row["metadata"]
        source = str(meta.get("file_name") or "未知檔案")
        page = meta.get("page", "未知")
        blocks.append(f"[片段 {i}｜來源：{source}｜頁碼：{page}]\n{row['text']}")
        print(f"Retrieval #{i}: {source} p.{page} rerank={row['score']:.3f}")
    return ask_gemini_llm(question, "\n\n".join(blocks), address_mode=address_mode)


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