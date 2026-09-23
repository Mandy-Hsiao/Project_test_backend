import os
import hashlib

from pathlib import Path
from types import SimpleNamespace

import httpx

from dotenv import load_dotenv


# ============================================================
# 1. 環境變數
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(
    ENV_PATH,
    override=False
)


# ============================================================
# 2. Timeout 設定
# ============================================================

CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 10.0
WRITE_TIMEOUT = 3.0
POOL_TIMEOUT = 3.0


# ============================================================
# 3. 讀取 API Keys
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
            "找不到 Gemini API Key。"
            "請確認 GEMINI_API_KEY_1、"
            "GEMINI_API_KEY_2 等環境變數。"
        )


    return keys


# ============================================================
# 4. Key 指紋
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
# 5. 取得 Gemini 回答
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


    texts = []

    for part in parts:

        text = part.get(
            "text"
        )

        if text:
            texts.append(text)


    return "\n".join(
        texts
    ).strip()


# ============================================================
# 6. Gemini Key Manager
# ============================================================

def create_gemini_interaction(
    prompt: str,
    model: str = "gemini-3.6-flash"
):

    if not prompt:

        raise ValueError(
            "prompt 不可為空"
        )


    api_keys = (
        load_gemini_api_keys()
    )


    print(
        "\n========================================"
    )

    print(
        f"Gemini Key Manager："
        f"找到 {len(api_keys)} 組 API Key"
    )

    print(
        "目前使用 REST generateContent"
    )

    print(
        "========================================"
    )


    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )


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

        ]

    }


    timeout = httpx.Timeout(

        connect=CONNECT_TIMEOUT,

        read=READ_TIMEOUT,

        write=WRITE_TIMEOUT,

        pool=POOL_TIMEOUT

    )


    last_error = None


    # ========================================================
    # 每個 Key 只嘗試一次
    # ========================================================

    for key_index, api_key in enumerate(
        api_keys,
        start=1
    ):

        fingerprint = (
            get_key_fingerprint(
                api_key
            )
        )


        print(
            f"\n嘗試 Gemini API Key "
            f"{key_index}/{len(api_keys)}"
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
                f"⏱️ Key {key_index} "
                "Gemini 呼叫逾時"
            )

            print(
                "➡️ 立即切換下一把 Key"
            )

            continue


        # ====================================================
        # Connection / Network
        # ====================================================

        except httpx.RequestError as exc:

            last_error = exc

            print(
                f"🌐 Key {key_index} "
                "Gemini 網路連線失敗"
            )

            print(
                "錯誤類型：",
                type(exc).__name__
            )

            print(
                "➡️ 立即切換下一把 Key"
            )

            continue


        status_code = (
            response.status_code
        )


        print(
            f"Gemini HTTP Status："
            f"{status_code}"
        )


        # ====================================================
        # 成功
        # ====================================================

        if status_code == 200:

            try:

                data = (
                    response.json()
                )

            except Exception as exc:

                last_error = exc

                print(
                    "❌ Gemini JSON "
                    "解析失敗"
                )

                continue


            output_text = (
                extract_output_text(
                    data
                )
            )


            if not output_text:

                last_error = RuntimeError(
                    "Gemini 沒有回傳有效文字"
                )

                print(
                    "⚠️ Gemini 沒有回傳文字"
                )

                continue


            print(
                f"✅ Gemini API Key "
                f"{key_index} 呼叫成功"
            )


            # 保持跟 rag_answer.py 相容
            return SimpleNamespace(
                output_text=output_text
            )


        # ====================================================
        # 取得 Gemini Error
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
        # ====================================================

        if status_code == 429:

            print(
                "⚠️ 此 Gemini Project "
                "已達 quota / rate limit"
            )

            print(
                "➡️ 立即切換下一把 Key"
            )

            continue


        # ====================================================
        # 401 / 403
        # ====================================================

        if status_code in (
            401,
            403
        ):

            print(
                "⚠️ API Key "
                "驗證或權限異常"
            )

            print(
                "➡️ 立即切換下一把 Key"
            )

            continue


        # ====================================================
        # 暫時性 Server Error
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
                "➡️ 不等待、不 Retry，"
                "直接切換下一把 Key"
            )

            continue


        # ====================================================
        # 其他錯誤
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
    # 全部失敗
    # ========================================================

    raise RuntimeError(
        "所有 Gemini API Key "
        "目前皆無法成功呼叫。\n"
        f"最後錯誤：{last_error}"
    )