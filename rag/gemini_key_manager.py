import os
import hashlib

from pathlib import Path
from types import SimpleNamespace

import httpx

from dotenv import load_dotenv


# ============================================================
# 1. 環境設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(
    BASE_DIR / ".env",
    override=False
)


# ============================================================
# 2. Timeout
# ============================================================

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 120.0
WRITE_TIMEOUT = 10.0
POOL_TIMEOUT = 5.0


# ============================================================
# 3. 記住目前正在使用哪一把 Key
#
# Vercel warm instance 期間可以保留
# 新 instance 重啟則會重新從 Key 1 開始
# ============================================================

_current_key_index = 0


# ============================================================
# 4. 讀取所有 Gemini API Key
# ============================================================

def load_gemini_api_keys():

    keys = []

    for index in range(1, 21):

        key = os.getenv(
            f"GEMINI_API_KEY_{index}"
        )

        if not key:
            continue

        key = key.strip()

        if (
            key
            and key not in keys
        ):
            keys.append(key)


    if not keys:

        raise RuntimeError(
            "找不到任何 Gemini API Key。"
            "請確認 GEMINI_API_KEY_1、"
            "GEMINI_API_KEY_2..."
        )


    return keys


# ============================================================
# 5. Key 指紋
#
# 只拿來看 Log
# 不會暴露 API Key
# ============================================================

def get_key_fingerprint(api_key):

    return (
        hashlib
        .sha256(
            api_key.encode("utf-8")
        )
        .hexdigest()[:8]
    )


# ============================================================
# 6. 從 Gemini REST Response 抓回答
# ============================================================

def extract_output_text(data):

    candidates = data.get(
        "candidates",
        []
    )

    if not candidates:
        return ""


    content = (
        candidates[0]
        .get(
            "content",
            {}
        )
    )

    parts = content.get(
        "parts",
        []
    )


    output_parts = []


    for part in parts:

        text = part.get(
            "text"
        )

        if text:

            output_parts.append(
                text
            )


    return "\n".join(
        output_parts
    ).strip()


# ============================================================
# 7. Gemini API Key 自動切換
#
# 注意：
# 這裡「完全不建立 Prompt」
#
# prompt 是 ask_gemini_llm()
# 已經整合完成後傳進來的。
# ============================================================

def create_gemini_interaction(
    prompt: str,
    model: str = "gemini-3.6-flash"
):

    global _current_key_index


    if not prompt:

        raise ValueError(
            "Gemini prompt 不可為空"
        )


    api_keys = (
        load_gemini_api_keys()
    )


    key_count = len(
        api_keys
    )


    print(
        "\n========================================"
    )

    print(
        f"Gemini Key Manager："
        f"找到 {key_count} 組 API Key"
    )

    print(
        "收到 ask_gemini_llm() "
        "整合完成的 Prompt"
    )

    print(
        f"Prompt 長度："
        f"{len(prompt)} 字元"
    )

    print(
        "========================================"
    )


    # ========================================================
    # Gemini REST API
    # ========================================================

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )


    # ========================================================
    # 這裡直接使用 ask_gemini_llm 傳來的 prompt
    #
    # 不新增、不修改、不覆蓋 Prompt
    # ========================================================

    payload = {

        "contents": [

            {

                "role": "user",

                "parts": [

                    {
                        "text": prompt
                    }

                ]

            }

        ],

        "generationConfig": {

            "temperature": 0.2,

            "maxOutputTokens": 4060

        }

    }


    timeout = httpx.Timeout(

        connect=CONNECT_TIMEOUT,

        read=READ_TIMEOUT,

        write=WRITE_TIMEOUT,

        pool=POOL_TIMEOUT

    )


    last_error = None
    start_key_index = _current_key_index

    # ========================================================
    # 從目前 Key 開始輪流嘗試
    # ========================================================

    for offset in range(
        key_count
    ):

        key_index = (
            start_key_index
            + offset
        ) % key_count

        api_key = (
            api_keys[key_index]
        )


        fingerprint = (
            get_key_fingerprint(
                api_key
            )
        )


        print(
            f"\n嘗試 Gemini API Key "
            f"{key_index + 1}/{key_count}"
        )

        print(
            f"Key 指紋："
            f"{fingerprint}"
        )


        headers = {

            "x-goog-api-key":
                api_key,

            "Content-Type":
                "application/json"

        }


        # ====================================================
        # 發送 Gemini Request
        # ====================================================

        try:

            with httpx.Client(
                timeout=timeout
            ) as client:

                response = (
                    client.post(
                        url,
                        headers=headers,
                        json=payload
                    )
                )


        # ====================================================
        # Timeout
        # ====================================================

        except httpx.TimeoutException as exc:

            last_error = exc


            print(
                f"⏱️ Key "
                f"{key_index + 1} "
                "呼叫 Timeout"
            )

            print(
                "➡️ 自動切換下一把 Key"
            )


            _current_key_index = (
                key_index + 1
            ) % key_count


            continue


        # ====================================================
        # Network Error
        # ====================================================

        except httpx.RequestError as exc:

            last_error = exc


            print(
                f"🌐 Key "
                f"{key_index + 1} "
                "發生網路錯誤："
                f"{type(exc).__name__}"
            )

            print(
                "➡️ 自動切換下一把 Key"
            )


            _current_key_index = (
                key_index + 1
            ) % key_count


            continue


        # ====================================================
        # HTTP Status
        # ====================================================

        status_code = (
            response.status_code
        )


        print(
            f"Gemini HTTP Status："
            f"{status_code}"
        )


        # ====================================================
        # 200 成功
        # ====================================================

        if status_code == 200:

            try:

                data = (
                    response.json()
                )

            except Exception as exc:

                last_error = exc

                print(
                    "❌ Gemini Response "
                    "JSON 解析失敗"
                )

                continue


            output_text = (
                extract_output_text(
                    data
                )
            )


            if not output_text:

                last_error = RuntimeError(
                    "Gemini 沒有回傳文字"
                )

                print(
                    "⚠️ Gemini 沒有回傳有效文字"
                )

                continue

            # =================================================
            # Token Usage
            # =================================================
            usage_metadata = data.get(
                "usageMetadata",
                {}
            )

            input_tokens = usage_metadata.get(
                "promptTokenCount",
                0
            )

            thinking_tokens = usage_metadata.get(
                "thoughtsTokenCount",
                0
            )

            output_tokens = usage_metadata.get(
                "candidatesTokenCount",
                0
            )

            total_tokens = usage_metadata.get(
                "totalTokenCount",
                0
            )


            print(
                f"Input Tokens：{input_tokens}"
            )

            print(
                f"Thinking Tokens：{thinking_tokens}"
            )

            print(
                f"Output Tokens：{output_tokens}"
            )

            print(
                f"Total Tokens：{total_tokens}"
            )


            # =================================================
            # 建立 Usage Object
            # =================================================

            usage = SimpleNamespace(
                total_input_tokens=input_tokens,
                thinking_tokens=thinking_tokens,
                total_output_tokens=output_tokens,
                total_tokens=total_tokens
            )


            # =================================================
            # 模擬 Gemini Interaction
            # =================================================

            return SimpleNamespace(
                output_text=output_text,
                usage=usage
            )


        # ====================================================
        # 解析錯誤內容
        # ====================================================

        try:

            error_data = (
                response.json()
            )

        except Exception:

            error_data = {

                "raw":
                    response.text[:1000]

            }


        last_error = RuntimeError(

            f"Gemini HTTP "
            f"{status_code}: "
            f"{error_data}"

        )


        # ====================================================
        # 429
        #
        # Quota / Rate Limit
        # ====================================================

        if status_code == 429:

            print(
                f"⚠️ Key "
                f"{key_index + 1} "
                "已達 quota / rate limit"
            )

            print(
                "➡️ 自動切換下一把 Key"
            )


            continue


        # ====================================================
        # 401 / 403
        #
        # API Key / Permission
        # ====================================================

        if status_code in (
            401,
            403
        ):

            print(
                f"⚠️ Key "
                f"{key_index + 1} "
                "驗證或權限異常"
            )

            print(
                "➡️ 自動切換下一把 Key"
            )

            continue


        # ====================================================
        # Gemini Server Error
        # ====================================================

        if status_code in (
            408,
            500,
            502,
            503,
            504
        ):

            print(
                f"⚠️ Gemini Server "
                f"回傳 {status_code}"
            )

            print(
                "➡️ 自動切換下一把 Key"
            )

            continue


        # ====================================================
        # 其他錯誤
        #
        # 400 / 404 通常不是換 Key 能解決
        # ====================================================

        print(
            "❌ Gemini 發生"
            "非備援型錯誤"
        )

        print(
            error_data
        )


        raise last_error


    # ========================================================
    # 所有 Key 都失敗
    # ========================================================

    print(
        "\n❌ 所有 Gemini API Key "
        "皆無法成功呼叫"
    )

    print(
        "最後錯誤：",
        repr(last_error)
    )


    raise RuntimeError(
        "所有 Gemini API Key "
        "目前皆無法成功呼叫。"
    )