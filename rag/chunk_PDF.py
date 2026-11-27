# ============================================================
# Python內建模組
# ============================================================
#從系統環境拿設定
import os
#處理文字規則
import re
#資料轉Json檔
import json
#UUID實際上沒用到
import uuid
import math
#找路徑用
from pathlib import Path
 
# ============================================================
# 第三方套件
# ============================================================
#讀 PDF
import pymupdf
#計算 Token
import tiktoken
#讀取 .env
from dotenv import load_dotenv
#建立Supabase Python 連線
from supabase import create_client
from openai import OpenAI

try:
    from .document_metadata import enrich_chunks
except ImportError:  # python rag/chunk_PDF.py
    from document_metadata import enrich_chunks


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(exist_ok=True)

load_dotenv(ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = os.getenv(
    "SUPABASE_BUCKET",
    "BeforeChunk_PDF"
)

if not SUPABASE_URL:
    raise ValueError(
        "找不到 SUPABASE_URL，請檢查 .env"
    )

if not SUPABASE_KEY:
    raise ValueError(
        "找不到 SUPABASE_KEY，請檢查 .env"
    )


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# 2. Tokenizer
# ============================================================

# 對 OpenAI / Azure OpenAI 常見模型而言
TOKENIZER = tiktoken.get_encoding(
    "cl100k_base"
)


def count_tokens(text):
    """
    計算文字 token 數量
    """

    if not text:
        return 0

    return len(
        TOKENIZER.encode(text)
    )


# ============================================================
# 3. 清理 PDF 文字
# ============================================================

def clean_text(text):
    """
    清理 PyMuPDF 取出的文字
    """

    if not text:
        return ""

    # 統一換行
    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    # Tab / 多餘空白
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # 過多空白行
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    # 每一行去除左右空白
    lines = []

    for line in text.split("\n"):
        line = line.strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def is_heading(line):
    """
    使用規則判斷文字是否像 SOP 標題。

    例如：
    1. VPN 設定
    1.1 帳號登入
    一、帳號設定
    (一) 下載軟體
    VPN 安裝說明
    """

    line = line.strip()

    if not line:
        return False

    # 太長通常不是標題
    if len(line) > 80:
        return False

    heading_patterns = [

        # 1. 數字 + . 開頭標題
        r"^\d+\.\s*\S+",

        # 1.1 多層數字編號標題
        r"^\d+\.\d+[\.\d]*\s*\S+",

        # 一、中文數字 + 頓號標題
        r"^[一二三四五六七八九十]+、\s*\S+",

        # (一) 括號中文數字標題
        r"^[\(（][一二三四五六七八九十]+[\)）]\s*\S+",

        # 1) 數字 + 右括號標題
        r"^\d+[\)）]\s*\S+",

        # Step 1
        r"^(step|STEP|Step)\s*\d+",

        # 第X章 / 第X節
        r"^第[一二三四五六七八九十\d]+[章節部分]"
    ] 
     
    for pattern in heading_patterns:

        if re.match(
            pattern,
            line
        ):
            return True

    # 沒有句號且很短，有機會是標題
    if (
        len(line) <= 30
        and not re.search(
            r"[。！？；，,]",
            line
        )
    ):
        return True

    return False


def split_page_into_sections(text):
    """
    清理頁面文字，標題只作為 metadata；不依標題切塊。

    回傳：
    [
        {
            "heading": "...",
            "text": "..."
        }
    ]
    """

    lines = text.split("\n")

    sections = []

    current_heading = ""
    current_lines = []

    # 同頁內容先保留在一起，避免短行／PDF 換行搶先切斷語意。
    # 第一個標題僅用於 metadata，實際切點交給 embedding 決定。
    for line in lines:
        line = line.strip()
        if not line or is_page_number(line) or is_export_datetime(line):
            continue
        if not current_heading and is_heading(line):
            current_heading = line
        current_lines.append(line)

    if current_lines:
        sections.append({
            "heading": current_heading,
            "text": "\n".join(current_lines)
        })

    return sections


# 語意切点分位數；只依語意距離分塊，不設定固定長度或 overlap。
SEMANTIC_BREAKPOINT_PERCENTILE = 90
embedding_client = None

def get_semantic_embeddings(parts):
    """沿用 build_db.py 的 Azure deployment，分批取得句子向量。"""
    global embedding_client
    if embedding_client is None:
        AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
        AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
        AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        )
        if not all((AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
                    AZURE_OPENAI_EMBEDDING_DEPLOYMENT)):
            raise ValueError("Semantic Chunking 需要既有的 Azure Embedding 三項 .env 設定")
        embedding_client = OpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            base_url=AZURE_OPENAI_ENDPOINT.rstrip("/") + "/openai/v1/"
        )

    embeddings = []
    for start in range(0, len(parts), 32):
        response = embedding_client.embeddings.create(
            model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            input=parts[start:start + 32]
        )
        data = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in data] != list(range(len(parts[start:start + 32]))):
            raise ValueError("Embedding 回傳筆數或順序不符，停止切塊")
        embeddings.extend(item.embedding for item in data)
    if any(not vector or not all(math.isfinite(value) for value in vector)
           or not any(vector) for vector in embeddings):
        raise ValueError("Embedding 向量無效，停止切塊")
    if len({len(vector) for vector in embeddings}) != 1:
        raise ValueError("Embedding 向量維度不一致，停止切塊")
    return embeddings


# 地址、電話、網址等精確資料不適合只靠語意相似度切割。
# 先保護含精確資訊的行及其前後標籤，避免「分公司名稱」與「地址」分離。
ADDRESS_RE = re.compile(
    r"(?:地址|住址|所在地|營業處所|辦公地點|通訊地址|聯絡地址|郵遞區號|"
    r"\d{3,6}\s*[^\n]{0,35}(?:路|街|大道|巷|弄|號|樓)|"
    r"(?:縣|市|區|鄉|鎮|村|里)[^\n]{0,45}(?:路|街|大道|巷|弄|號|樓))"
)
EXACT_RE = re.compile(r"(?:地址|電話|傳真|分機|郵遞區號|統編|網址|https?://|www\.)", re.I)
ENTITY_RE = re.compile(r"(?:分公司|分行|營業部|服務處|辦公室|總公司|總部|據點|中心|機房|部門|單位|門市)")


def extract_exact_fields(text):
    """保留原文精確欄位；不推測或補完缺漏的地址。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    addresses = []
    for line in lines:
        if ADDRESS_RE.search(line):
            addresses.append(line)
    return list(dict.fromkeys(addresses))


def protect_exact_lines(text):
    """將名稱 + 地址/電話等資訊合併為不可分割的語意候選段落。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    groups = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if EXACT_RE.search(line) or ADDRESS_RE.search(line):
            # 向前帶入緊鄰的單位名稱，避免檢索只命中地址卻不知道是哪個單位。
            if groups and ENTITY_RE.search(groups[-1]) and len(groups[-1]) <= 100:
                line = groups.pop() + "\n" + line
            # 同一筆資料連續出現的地址/電話/郵遞區號不拆散。
            while i + 1 < len(lines) and (EXACT_RE.search(lines[i + 1]) or ADDRESS_RE.search(lines[i + 1])):
                i += 1
                line += "\n" + lines[i]
            groups.append(line)
        else:
            groups.append(line)
        i += 1
    return groups


def split_semantic_candidates(text):
    """一般敘述按句分割；精確資料整組保留。"""
    candidates = []
    for group in protect_exact_lines(text):
        if EXACT_RE.search(group) or ADDRESS_RE.search(group):
            candidates.append(group)
        else:
            candidates.extend(
                part.strip() for part in re.findall(
                    r"[^。！？!?；;]+(?:[。！？!?；;]+|$)", group
                ) if part.strip()
            )
    return candidates


def semantic_token_split(text):
    """以相鄰句子的 cosine distance 決定單層 chunk 邊界。

    換行和標點僅提供句子候選；不使用遞迴、長度切塊或 overlap。
    單句或單一語意區段可超過舊版 350/1000 token，且不會強制截斷。
    """
    text = text.strip()
    if not text:
        return []
    separators = r"[^。！？!?；;\n]+(?:[。！？!?；;]+|\n+|$)|[。！？!?；;]+"
    parts = split_semantic_candidates(text)
    if len(parts) <= 1:
        return parts
    embeddings = get_semantic_embeddings(parts)
    distances = []
    for index in range(len(embeddings) - 1):
        left, right = embeddings[index:index + 2]
        similarity = sum(a * b for a, b in zip(left, right)) / (
            math.sqrt(sum(a * a for a in left)) *
            math.sqrt(sum(b * b for b in right))
        )
        distances.append(1 - max(-1.0, min(1.0, similarity)))
    values = sorted(distances)
    position = (len(values) - 1) * SEMANTIC_BREAKPOINT_PERCENTILE / 100
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    threshold = values[lower] + (values[upper] - values[lower]) * (position - lower)
    varying_distances = max(distances) - min(distances) > 1e-9
    chunks = []
    current_chunk = parts[0]
    for index, part in enumerate(parts[1:], start=1):
        # 地址段落之前的單位名稱不可被語意斷點切開。
        protect_boundary = bool(
            (ADDRESS_RE.search(part) or EXACT_RE.search(part))
            and ENTITY_RE.search(current_chunk.split("\n")[-1])
            and len(current_chunk) <= 160
        )
        if varying_distances and distances[index - 1] >= threshold and not protect_boundary:
            chunks.append(current_chunk)
            current_chunk = part
        else:
            current_chunk += "\n" + part
    chunks.append(current_chunk)
    return chunks


def create_semantic_chunks(section_text, heading, file_name, storage_path,
                           page_number, section_index):
    results = []
    source_id = uuid.uuid5(uuid.NAMESPACE_URL, storage_path).hex[:8]
    for chunk_index, text in enumerate(semantic_token_split(section_text), start=1):
        chunk_id = (f"{Path(file_name).stem}_{source_id}_p{page_number}"
                    f"_s{section_index}_semantic{chunk_index}")
        results.append({
            "chunk_id": chunk_id,
            "file_name": file_name,
            "storage_path": storage_path,
            "page": page_number,
            "section_title": heading,
            "content_type": "text",
            "token_count": count_tokens(text),
            "text": text,
            # 下游 build_db.py 可將此欄位寫入 Pinecone metadata；
            # 即使尚未修改 build_db，原始 text 仍完整保留地址。
            "exact_address_lines": extract_exact_fields(text),
        })
    return results

def is_page_number(text):

    text = text.strip()

    return bool(
        re.fullmatch(
            r"\d+\s*/\s*\d+",
            text
        )
    )


def is_export_datetime(text):

    text = text.strip()

    return bool(
        re.fullmatch(
            r"\d{4}/\d{1,2}/\d{1,2}\s+.*\d{1,2}:\d{2}",
            text
        )
    )


def process_pdf(
    pdf_bytes,
    file_name,
    storage_path
):

    doc = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    document_results = []

    try:
        for page_index, page in enumerate(
            doc
        ):

            page_number = (
                page_index + 1
            )

            raw_text = page.get_text(
                "text"
            )

            text = clean_text(
                raw_text
            )

            # 完全沒文字
            if not text:

                print(
                    f"  第 {page_number} 頁無可讀文字，跳過"
                )

                continue

            sections = (
                split_page_into_sections(
                    text
                )
            )

            print(
                f"  第 {page_number} 頁："
                f"{len(sections)} 個 section"
            )

            for section_index, section in enumerate(
                sections,
                start=1
            ):

                section_text = (
                    section["text"].strip()
                )

                # 沒有文字就跳過
                if is_page_number(section_text):
                    print(
                        f"    跳過頁碼：{section_text}"
                    )
                    continue

                if is_export_datetime(section_text):
                    print(
                        f"    跳過日期：{section_text}"
                    )
                    continue

                print(
                    f"    Section {section_index}："
                    f"{section_text[:50]}"
                )

                results = (
                    create_semantic_chunks(
                        section_text=section_text,
                        heading=section["heading"],
                        file_name=file_name,
                        storage_path=storage_path,
                        page_number=page_number,
                        section_index=section_index
                    )
                )

                document_results.extend(
                    results
                )

    finally:
        doc.close()

    # 每份 PDF 產出後統一加入同一份文件的身分與前後 Chunk 連結。
    return enrich_chunks(document_results)

def list_pdf_files(folder=""):
    """用迭代方式掃描 Storage 資料夾；與文字切塊無關。"""
    pdf_files = []
    folders = [folder]
    while folders:
        folder = folders.pop()
        offset = 0
        while True:
            items = supabase.storage.from_(BUCKET_NAME).list(
                folder, {"limit": 1000, "offset": offset}
            )
            for item in items:
                name = item.get("name")
                if not name:
                    continue
                storage_path = f"{folder}/{name}" if folder else name
                if item.get("id") is None:
                    folders.append(storage_path)
                elif name.lower().endswith(".pdf"):
                    pdf_files.append({"file_name": name, "storage_path": storage_path})
            if len(items) < 1000:
                break
            offset += 1000
    return pdf_files

def download_pdf(
    storage_path
):

    pdf_bytes = (
        supabase
        .storage
        .from_(BUCKET_NAME)
        .download(
            storage_path
        )
    )

    return pdf_bytes


def process_all_pdfs():

    pdf_files = (
        list_pdf_files()
    )

    print(
        f"\n找到 {len(pdf_files)} 份 PDF"
    )

    all_results = []

    for index, pdf_info in enumerate(
        pdf_files,
        start=1
    ):

        file_name = (
            pdf_info["file_name"]
        )

        storage_path = (
            pdf_info["storage_path"]
        )

        print("\n" + "=" * 70)

        print(
            f"[{index}/{len(pdf_files)}] "
            f"正在處理：{storage_path}"
        )

        try:

            pdf_bytes = (
                download_pdf(
                    storage_path
                )
            )

            print(
                f"下載完成："
                f"{len(pdf_bytes)} bytes"
            )

            results = (
                process_pdf(
                    pdf_bytes=pdf_bytes,
                    file_name=file_name,
                    storage_path=storage_path
                )
            )

            print(f"Semantic Chunk：{len(results)}")

            all_results.extend(
                results
            )

        except Exception as e:

            print(
                f"處理 {storage_path} "
                f"發生錯誤：{e}"
            )
            # 不儲存不完整結果，避免 Embedding 失敗後覆蓋原 JSON。
            raise

    return all_results


def save_results(results):
    output_path = OUTPUT_DIR / "semantic_chunks.json"
    temporary_path = output_path.with_suffix(".json.tmp")
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    temporary_path.replace(output_path)
    print(f"\nChunk 資料已儲存：{output_path}")


def print_preview(results, limit=3):
    for item in results[:limit]:
        print("\nChunk ID：", item["chunk_id"])
        print("檔案：", item["file_name"])
        print("頁碼：", item["page"])
        print("Tokens：", item["token_count"])
        print("Text：", item["text"][:300])


if __name__ == "__main__":
    results = process_all_pdfs()
    print(f"\n全部處理完成，Semantic Chunk 總數：{len(results)}")
    save_results(results)
    print_preview(results)