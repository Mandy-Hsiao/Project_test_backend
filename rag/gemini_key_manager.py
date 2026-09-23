import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# 1. 載入 .env
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(
    ENV_PATH,
    override=False
)


# ============================================================
# 2. 讀取所有 Gemini API Keys
# ============================================================

def load_gemini_api_keys():

    keys = []

    # 最多讀取 GEMINI_API_KEY_1 ~ GEMINI_API_KEY_20
    for index in range(1, 21):

        key = os.getenv(
            f"GEMINI_API_KEY_{index}"
        )

        if key:

            key = key.strip()

            if (
                key
                and key not in keys
            ):
                keys.append(key)


    # --------------------------------------------------------
    # 向下相容舊設定
    # 如果還有 GEMINI_API_KEY，也會自動加入
    # --------------------------------------------------------

    legacy_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if legacy_key:

        legacy_key = legacy_key.strip()

        if (
            legacy_key
            and legacy_key not in keys
        ):
            keys.append(
                legacy_key
            )


    if not keys:

        raise RuntimeError(
            "找不到任何 Gemini API Key。\n"
            "請確認 .env 中至少存在：\n"
            "GEMINI_API_KEY_1=..."
        )


    return keys


# ============================================================
# 3. 取得 API Error 的 HTTP Status Code
# ============================================================

def get_error_code(exc):

    # --------------------------------------------------------
    # 先嘗試直接讀 exception 的屬性
    # --------------------------------------------------------

    for attribute in (
        "status_code",
        "code"
    ):

        value = getattr(
            exc,
            attribute,
            None
        )

        if value is not None:

            try:
                return int(value)

            except (
                TypeError,
                ValueError
            ):
                pass


    # --------------------------------------------------------
    # 如果 SDK 沒提供 code，
    # 就從錯誤文字中找 HTTP code
    # --------------------------------------------------------

    error_text = str(exc)

    patterns = [

        r"Error code:\s*(\d{3})",

        r"'code':\s*'?(401|403|404|429|500|502|503|504)'?",

        r'"code":\s*"?(401|403|404|429|500|502|503|504)"?',

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            error_text
        )

        if match:

            return int(
                match.group(1)
            )


    return None


# ============================================================
# 4. Gemini API Key Manager
# ============================================================

def create_gemini_interaction(
    prompt: str,
    model: str = "gemini-3.6-flash",
    max_503_retries: int = 1
):

    """
    Gemini API 自動備援。

    行為：

    成功
        → 直接回傳 interaction

    429
        → 此 Project 遇到 quota / rate limit
        → 換下一個 API Key

    401 / 403
        → Key 或權限問題
        → 換下一個 API Key

    503
        → Gemini 暫時繁忙
        → 同一個 Key 先 retry
        → retry 仍失敗才換下一個 Key

    其他錯誤
        → 不盲目切換 Key
        → 直接拋出原錯誤
    """


    if not prompt:

        raise ValueError(
            "prompt 不可為空"
        )


    api_keys = (
        load_gemini_api_keys()
    )


    print(
        f"\nGemini Key Manager："
        f"找到 {len(api_keys)} 組 API Key"
    )


    last_error = None


    # ========================================================
    # 逐一嘗試每一把 Key
    # ========================================================

    for key_index, api_key in enumerate(
        api_keys,
        start=1
    ):

        print(
            f"\n嘗試 Gemini API Key "
            f"{key_index}/{len(api_keys)}"
        )


        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=1
                )
            )
        )


        try:

            # =================================================
            # 503 retry
            # =================================================

            for retry_index in range(
                max_503_retries + 1
            ):

                try:

                    interaction = (
                        client
                        .interactions
                        .create(
                            model=model,
                            input=prompt,
                            timeout=20
                        )
                    )


                    print(
                        f"✅ Gemini API Key "
                        f"{key_index} 呼叫成功"
                    )


                    return interaction


                except Exception as exc:

                    last_error = exc

                    error_code = (
                        get_error_code(exc)
                    )


                    print(
                        f"Gemini Key "
                        f"{key_index} "
                        f"發生錯誤："
                        f"{error_code}"
                    )


                    # =========================================
                    # 503
                    # Gemini server 暫時繁忙
                    # =========================================

                    if error_code == 503:

                        if (
                            retry_index
                            < max_503_retries
                        ):

                            wait_seconds = (
                                2 ** retry_index
                            )

                            print(
                                "Gemini 服務目前繁忙，"
                                f"{wait_seconds} 秒後"
                                "使用同一把 Key 重試..."
                            )


                            time.sleep(
                                wait_seconds
                            )

                            continue


                        print(
                            "503 重試次數已達上限，"
                            "改用下一把 Key。"
                        )

                        break


                    # =========================================
                    # 429
                    # Quota / Rate Limit
                    # =========================================

                    elif error_code == 429:

                        print(
                            "⚠️ 此 Gemini Project "
                            "目前遇到 quota / rate limit。"
                        )

                        print(
                            "自動切換下一把 API Key..."
                        )

                        break


                    # =========================================
                    # 401 / 403
                    # API Key 或權限異常
                    # =========================================

                    elif error_code in (
                        401,
                        403
                    ):

                        print(
                            "⚠️ 此 API Key "
                            "驗證或權限異常。"
                        )

                        print(
                            "自動切換下一把 API Key..."
                        )

                        break


                    # =========================================
                    # 其他錯誤
                    # =========================================

                    else:

                        print(
                            "❌ 發生非備援型錯誤，"
                            "停止自動切換。"
                        )

                        raise


        finally:

            try:

                client.close()

            except Exception:

                pass


    # ========================================================
    # 所有 Key 都失敗
    # ========================================================

    raise RuntimeError(
        "所有 Gemini API Key "
        "目前皆無法成功呼叫。\n"
        f"最後錯誤：{last_error}"
    )