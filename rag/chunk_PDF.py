import os
import re
import json
import uuid
from pathlib import Path

import pymupdf
import tiktoken

from dotenv import load_dotenv
from supabase import create_client


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

# 對 OpenAI / Azure OpenAI 常見模型而言，
# cl100k_base 是相對安全的通用選擇。
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


# ============================================================
# 4. 判斷一行是不是標題
# ============================================================

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

        # 1. 標題
        r"^\d+\.\s*\S+",

        # 1.1 標題
        r"^\d+\.\d+[\.\d]*\s*\S+",

        # 一、標題
        r"^[一二三四五六七八九十]+、\s*\S+",

        # (一) 標題
        r"^[\(（][一二三四五六七八九十]+[\)）]\s*\S+",

        # 1) 標題
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


# ============================================================
# 5. 將每頁文字切成 Section
# ============================================================

def split_page_into_sections(text):
    """
    根據標題與段落切分。

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

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if is_heading(line):

            # 前面已有內容
            if current_lines:

                sections.append({
                    "heading": current_heading,
                    "text": "\n".join(
                        current_lines
                    )
                })

                current_lines = []

            current_heading = line

            current_lines.append(line)

        else:

            current_lines.append(line)

    if current_lines:

        sections.append({
            "heading": current_heading,
            "text": "\n".join(
                current_lines
            )
        })

    return sections


# ============================================================
# 6. Recursive Token Chunker
# ============================================================

def recursive_token_split(
    text,
    max_tokens=350,
    overlap_tokens=50
):
    """
    Recursive Token Chunking。

    優先依：
    段落
    ↓
    換行
    ↓
    句號
    ↓
    逗號
    ↓
    token 強制切割
    """

    separators = [
        "\n\n",
        "\n",
        "。",
        "！",
        "？",
        "；",
        "，",
        " "
    ]

    return recursive_split_by_separator(
        text=text,
        separators=separators,
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens
    )


def recursive_split_by_separator(
    text,
    separators,
    max_tokens,
    overlap_tokens
):

    text = text.strip()

    if not text:
        return []

    # 已符合限制
    if count_tokens(text) <= max_tokens:
        return [text]

    # 所有 separator 都用完
    if not separators:

        return force_token_split(
            text,
            max_tokens,
            overlap_tokens
        )

    separator = separators[0]

    parts = text.split(separator)

    # 如果根本切不開
    if len(parts) == 1:

        return recursive_split_by_separator(
            text=text,
            separators=separators[1:],
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens
        )

    chunks = []

    current_chunk = ""

    for part in parts:

        part = part.strip()

        if not part:
            continue

        if current_chunk:

            candidate = (
                current_chunk
                + separator
                + part
            )

        else:

            candidate = part

        # 還沒超過 token 上限
        if (
            count_tokens(candidate)
            <= max_tokens
        ):

            current_chunk = candidate

        else:

            # 儲存目前 chunk
            if current_chunk:

                if (
                    count_tokens(current_chunk)
                    <= max_tokens
                ):

                    chunks.append(
                        current_chunk
                    )

                else:

                    sub_chunks = (
                        recursive_split_by_separator(
                            text=current_chunk,
                            separators=separators[1:],
                            max_tokens=max_tokens,
                            overlap_tokens=overlap_tokens
                        )
                    )

                    chunks.extend(
                        sub_chunks
                    )

            current_chunk = part

    # 最後一段
    if current_chunk:

        if (
            count_tokens(current_chunk)
            <= max_tokens
        ):

            chunks.append(
                current_chunk
            )

        else:

            chunks.extend(
                recursive_split_by_separator(
                    text=current_chunk,
                    separators=separators[1:],
                    max_tokens=max_tokens,
                    overlap_tokens=overlap_tokens
                )
            )

    return add_token_overlap(
        chunks,
        overlap_tokens
    )


# ============================================================
# 7. Token 強制切割
# ============================================================

def force_token_split(
    text,
    max_tokens,
    overlap_tokens
):

    token_ids = TOKENIZER.encode(
        text
    )

    chunks = []

    start = 0

    step = (
        max_tokens
        - overlap_tokens
    )

    if step <= 0:
        raise ValueError(
            "overlap_tokens 必須小於 max_tokens"
        )

    while start < len(token_ids):

        end = (
            start
            + max_tokens
        )

        chunk_tokens = (
            token_ids[start:end]
        )

        chunk_text = (
            TOKENIZER.decode(
                chunk_tokens
            )
        )

        chunks.append(
            chunk_text.strip()
        )

        start += step

    return chunks


# ============================================================
# 8. Child overlap
# ============================================================

def add_token_overlap(
    chunks,
    overlap_tokens
):
    """
    在 Child Chunk 之間保留少量 token overlap
    """

    if (
        overlap_tokens <= 0
        or len(chunks) <= 1
    ):
        return chunks

    result = []

    previous_tokens = []

    for index, chunk in enumerate(chunks):

        current_tokens = (
            TOKENIZER.encode(chunk)
        )

        if index == 0:

            result.append(chunk)

        else:

            overlap = (
                previous_tokens[
                    -overlap_tokens:
                ]
            )

            merged_tokens = (
                overlap
                + current_tokens
            )

            merged_text = (
                TOKENIZER.decode(
                    merged_tokens
                )
            )

            result.append(
                merged_text.strip()
            )

        previous_tokens = (
            current_tokens
        )

    return result


# ============================================================
# 9. 建立 Parent / Child
# ============================================================

def create_parent_child_chunks(
    section_text,
    heading,
    file_name,
    storage_path,
    page_number,
    parent_max_tokens=1000,
    child_max_tokens=350,
    child_overlap_tokens=50
):
    """
    一個 Section 會先當 Parent。

    如果 Parent 過長，
    先切成多個 Parent。

    再把 Parent 切成 Child。
    """

    results = []

    # Parent 也不能無限大
    parent_parts = (
        recursive_token_split(
            section_text,
            max_tokens=parent_max_tokens,
            overlap_tokens=100
        )
    )

    for parent_index, parent_text in enumerate(
        parent_parts
    ):

        parent_id = (
            f"{Path(file_name).stem}"
            f"_p{page_number}"
            f"_parent{parent_index + 1}"
        )

        # Child Chunk
        child_chunks = (
            recursive_token_split(
                parent_text,
                max_tokens=child_max_tokens,
                overlap_tokens=child_overlap_tokens
            )
        )

        parent_data = {
            "parent_id": parent_id,
            "file_name": file_name,
            "storage_path": storage_path,
            "page_start": page_number,
            "page_end": page_number,
            "section_title": heading,
            "token_count": count_tokens(
                parent_text
            ),
            "text": parent_text
        }

        children = []

        for child_index, child_text in enumerate(
            child_chunks
        ):

            child_id = (
                f"{parent_id}"
                f"_child{child_index + 1}"
            )

            child_data = {
                "child_id": child_id,
                "parent_id": parent_id,
                "file_name": file_name,
                "storage_path": storage_path,
                "page": page_number,
                "section_title": heading,
                "content_type": "text",
                "token_count": count_tokens(
                    child_text
                ),
                "text": child_text
            }

            children.append(
                child_data
            )

        results.append({
            "parent": parent_data,
            "children": children
        })

    return results


# ============================================================
# 10. 解析單一 PDF
# ============================================================

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

        for section in sections:

            section_text = (
                section["text"]
            )

            if not section_text:
                continue

            results = (
                create_parent_child_chunks(
                    section_text=section_text,
                    heading=section["heading"],
                    file_name=file_name,
                    storage_path=storage_path,
                    page_number=page_number
                )
            )

            document_results.extend(
                results
            )

    doc.close()

    return document_results


# ============================================================
# 11. Supabase Storage 遞迴掃描
# ============================================================

def list_pdf_files_recursive(
    folder=""
):
    """
    遞迴掃描 Bucket 內所有資料夾。

    Supabase 官方 Python SDK 支援
    list(path) 的寫法。
    """

    pdf_files = []

    items = (
        supabase
        .storage
        .from_(BUCKET_NAME)
        .list(
            folder,
            {
                "limit": 1000,
                "offset": 0
            }
        )
    )

    for item in items:

        name = item.get(
            "name"
        )

        if not name:
            continue

        if folder:

            storage_path = (
                f"{folder}/{name}"
            )

        else:

            storage_path = name

        # Supabase folder 通常沒有 id
        item_id = item.get(
            "id"
        )

        if item_id is None:

            # 當成資料夾繼續掃描
            child_files = (
                list_pdf_files_recursive(
                    storage_path
                )
            )

            pdf_files.extend(
                child_files
            )

        else:

            if name.lower().endswith(
                ".pdf"
            ):

                pdf_files.append({
                    "file_name": name,
                    "storage_path": storage_path
                })

    return pdf_files




# ============================================================
# 12. 下載 PDF
# ============================================================

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




# ============================================================
# 13. 處理全部 PDF
# ============================================================

def process_all_pdfs():

    pdf_files = (
        list_pdf_files_recursive()
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

            parent_count = len(
                results
            )

            child_count = sum(
                len(
                    item["children"]
                )
                for item in results
            )

            print(
                f"Parent：{parent_count}"
            )

            print(
                f"Child：{child_count}"
            )

            all_results.extend(
                results
            )

        except Exception as e:

            print(
                f"處理 {storage_path} "
                f"發生錯誤：{e}"
            )

    return all_results


# ============================================================
# 14. 儲存 JSON
# ============================================================

def save_results(
    results
):

    output_path = (
        OUTPUT_DIR
        / "parent_child_chunks.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"\nChunk 資料已儲存："
        f"{output_path}"
    )


# ============================================================
# 15. 顯示測試結果
# ============================================================

def print_preview(
    results,
    limit=3
):

    print("\n" + "=" * 70)
    print("Chunk Preview")
    print("=" * 70)

    count = 0

    for item in results:

        parent = item["parent"]

        print(
            "\nParent ID：",
            parent["parent_id"]
        )

        print(
            "檔案：",
            parent["file_name"]
        )

        print(
            "頁碼：",
            parent["page_start"]
        )

        print(
            "Section：",
            parent["section_title"]
        )

        print(
            "Parent Tokens：",
            parent["token_count"]
        )

        for child in item["children"]:

            print(
                "\n  Child ID：",
                child["child_id"]
            )

            print(
                "  Tokens：",
                child["token_count"]
            )

            print(
                "  Text："
            )

            print(
                "  ",
                child["text"][:300]
            )

        count += 1

        if count >= limit:
            break


# ============================================================
# 16. Main
# ============================================================

if __name__ == "__main__":

    results = (
        process_all_pdfs()
    )

    parent_count = len(
        results
    )

    child_count = sum(
        len(
            item["children"]
        )
        for item in results
    )

    print("\n" + "=" * 70)

    print(
        f"全部處理完成"
    )

    print(
        f"Parent 總數："
        f"{parent_count}"
    )

    print(
        f"Child 總數："
        f"{child_count}"
    )

    save_results(
        results
    )

    print_preview(
        results
    )