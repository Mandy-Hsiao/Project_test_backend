"""Document-level identity and sibling links for Semantic Chunks.

This module is intentionally offline: it can enrich an existing JSON without
calling Supabase, Azure OpenAI, Pinecone, or Gemini.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import re
import uuid


JOB_TITLE = re.compile(r"^證券公司[^\n]{2,50}(?:人員|工程師|管理師)(?:[（(][^\n]{1,30}[）)])?$")
TITLE_TERMS = re.compile(r"(?:規範|基準|辦法|指南|作業程序|操作說明|操作手冊)$")


def infer_document_identity(file_name: str, first_page_text: str) -> tuple[str, str]:
    """Return (document_title, document_type) based on *source* text.

    Avoid invented titles: when text does not identify a title, use the file stem.
    """
    stem = Path(file_name).stem
    lines = [line.strip() for line in first_page_text.splitlines() if line.strip()]
    head = "\n".join(lines[:100])
    normalized = head.lower()

    if "104人力銀行" in head and ("職務類別" in head or "證券公司" in head):
        candidates = []
        for line in lines[:90]:
            if (JOB_TITLE.match(line) and "…" not in line and "..." not in line
                    and "｜" not in line and "|" not in line):
                candidates.append(line)
        if candidates:
            # Prefer an explicit and complete posting name over truncated browser titles.
            return max(candidates, key=len), "job_posting"
        return stem, "job_posting"

    if "首頁 / 關於我們 / 公司簡介" in head or stem.lower() == "company":
        return "兆豐證券－公司簡介", "company_profile"
    if "營業據點" in head or stem.lower() == "location":
        return "兆豐證券－營業據點", "locations"
    if "組織架構" in head or stem.lower() == "instruction":
        return "兆豐證券－組織架構", "organization"
    if "幸福職場" in head or stem.lower() in {"benifit", "benefit"}:
        return "兆豐證券－薪酬與福利", "benefits"

    # Regulations often have multiple approval dates before the real heading.
    for line in lines[:35]:
        if 5 <= len(line) <= 56 and TITLE_TERMS.search(line) and not re.match(r"^[一二三四五六七八九十\d]+[.、]", line):
            return line, "regulation"

    for line in lines[:12]:
        if 4 <= len(line) <= 65 and ("設定" in line or "教學" in line or "SOP" in line):
            return line, "sop"

    return stem, "reference"


def enrich_chunks(chunks: list[dict]) -> list[dict]:
    """Add a shared document ID/title/type and adjacent chunk IDs.

    Preserves all old chunk IDs and text, so existing JSON can be migrated safely.
    The links are only among chunks with the SAME storage_path.
    """
    if not isinstance(chunks, list):
        raise ValueError("chunks 必須是 list")
    by_path: OrderedDict[str, list[dict]] = OrderedDict()
    used_ids: set[str] = set()

    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ValueError("每筆 chunk 必須是 dict")
        cid = chunk.get("chunk_id")
        path = chunk.get("storage_path") or chunk.get("file_name")
        if not isinstance(cid, str) or not cid or not isinstance(path, str) or not path:
            raise ValueError("chunk_id / storage_path 不可空白")
        if cid in used_ids:
            raise ValueError(f"chunk_id 重複：{cid}")
        used_ids.add(cid)
        by_path.setdefault(path, []).append(chunk)

    # Do not change original ordering of the JSON file.
    metadata_by_id: dict[str, dict] = {}
    for path, document_chunks in by_path.items():
        first_page = min(int(chunk.get("page", 1)) for chunk in document_chunks)
        first_page_text = "\n".join(
            str(chunk.get("text", "")) for chunk in document_chunks
            if int(chunk.get("page", 1)) == first_page
        )
        file_name = str(document_chunks[0].get("file_name") or Path(path).name)
        title, doc_type = infer_document_identity(file_name, first_page_text)
        document_id = "doc_" + uuid.uuid5(uuid.NAMESPACE_URL, path).hex
        for i, chunk in enumerate(document_chunks):
            metadata_by_id[chunk["chunk_id"]] = {
                "document_id": document_id,
                "document_title": title,
                "document_type": doc_type,
                "chunk_seq": i,
                "document_chunk_count": len(document_chunks),
                "prev_chunk_id": document_chunks[i - 1]["chunk_id"] if i else "",
                "next_chunk_id": (document_chunks[i + 1]["chunk_id"]
                                  if i + 1 < len(document_chunks) else ""),
            }

    return [{**chunk, **metadata_by_id[chunk["chunk_id"]]} for chunk in chunks]
