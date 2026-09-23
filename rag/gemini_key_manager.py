import os
import re
import hashlib
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# 1. 載入環境變數
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(
    ENV_PATH,
    override=False
)


# ============================================================
# 2. 讀取 Gemini API Keys
# ============================================================

def load_gemini_api_keys():

    keys = []

    # GEMINI_API_KEY_1 ~ GEMINI_API_KEY_20
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
            "找不到任何 Gemini API Key。\n"
            "請確認環境變數至少存在：\n"
            "GEMINI_API_KEY_1"
        )


    return keys


# ============================================================
# 3. Key 指紋
#    不直接輸出 API Key
# ============================================================

def get_key_fingerprint(
    api_key: str
) -> str:

    return (
        hashlib
        .sha256(
            api_key.encode("utf-8")
        )
        .hexdigest()[:8]
    )


# ============================================================
# 4. 解析 HTTP Error Code
# ============================================================

def get_error_code(exc):

    # --------------------------------------------------------
    # Exception 本身
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
    # Exception.response
    # --------------------------------------------------------

    response = getattr(
        exc,
        "response",
        None
    )

    if response is not None:

        value = getattr(
            response,
            "status_code",
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
    # 從錯誤文字解析
    # --------------------------------------------------------

    error_text = str(exc)

    patterns = [

        r"Error code:\s*(\d{3})",

        r"status[_ ]?code[=:]\s*(\d{3})",

        r"HTTP[/\d. ]+(\d{3})",

        r"'code':\s*'?"
        r"(400|401|403|404|408|409|429|500|502|503|504)"
        r"'?",

        r'"code":\s*"'
        r"?(400|401|403|404|408|409|429|500|502|503|504)"
        r'"?',

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            error_text,
            re.IGNORECASE
        )

        if match:

            return int(
                match.group(1)
            )


    return None


# ============================================================
# 5. 判斷是否為網路 / Timeout
# ============================================================

def is_network_or_timeout_error(
    exc
):

    exception_name = (
        type(exc).__name__
        .lower()
    )

    error_text = (
        str(exc)
        .lower()
    )


    keywords = (

        "timeout",
        "timed out",

        "readtimeout",
        "connecttimeout",

        "connection",
        "connection reset",

        "network",

        "server disconnected",

        "remote protocol",

        "temporarily unavailable",

        "service unavailable",

    )


    for keyword in keywords:

        if (
            keyword in exception_name
            or keyword in error_text
        ):

            return True


    return False


# ============================================================
# 6. Gemini API Key Manager
# ============================================================

def create_gemini_interaction(
    prompt: str,
    model: str = "gemini-3.6-flash"
):

    """
    Fail-Fast Gemini API Key Manager

    行為：

    200
        → 直接回傳

    429
        → 立刻切換下一把 Key

    401 / 403
        → Key / 權限問題
        → 立刻切換下一把 Key

    408 / 500 / 502 / 503 / 504
        → 暫時性服務錯誤
        → 立刻切換下一把 Key

    Timeout / Connection / code=None
        → 不等待
        → 立刻切換下一把 Key

    400 / 404 等
        → 通常是程式、Model 或 Request 問題
        → 不應靠換 Key 解決
        → 直接拋出
    """


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
        "========================================"
    )


    last_error = None


    # ========================================================
    # 每把 Key 最多只呼叫一次
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
            f"Key 指紋：{fingerprint}"
        )


        # ====================================================
        # 關閉 Google SDK 自動 retry
        #
        # timeout = 15000 ms
        # attempts = 1 表示不額外 retry
        # ====================================================

        client = genai.Client(

            api_key=api_key,

            http_options=types.HttpOptions(

                timeout=15000,

                retry_options=(
                    types.HttpRetryOptions(
                        attempts=1
                    )
                )

            )

        )


        try:

            # =================================================
            # Gemini Request
            #
            # timeout=15：
            # interactions.create 的 timeout 單位是秒
            # =================================================

            interaction = (
                client
                .interactions
                .create(
                    model=model,
                    input=prompt,
                    timeout=15
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

            network_error = (
                is_network_or_timeout_error(
                    exc
                )
            )


            print(
                f"\nGemini Key "
                f"{key_index} 呼叫失敗"
            )

            print(
                "錯誤 Code：",
                error_code
            )

            print(
                "錯誤 Type：",
                type(exc).__name__
            )

            print(
                "錯誤訊息：",
                str(exc)
            )


            # ================================================
            # 429
            # ================================================

            if error_code == 429:

                print(
                    "⚠️ 此 Gemini Project "
                    "已達 quota / rate limit。"
                )

                print(
                    "➡️ 立即切換下一把 Key。"
                )

                continue


            # ================================================
            # 401 / 403
            # ================================================

            if error_code in (
                401,
                403
            ):

                print(
                    "⚠️ 此 Gemini Key "
                    "驗證或權限異常。"
                )

                print(
                    "➡️ 立即切換下一把 Key。"
                )

                continue


            # ================================================
            # Temporary HTTP Errors
            # ================================================

            if error_code in (
                408,
                500,
                502,
                503,
                504
            ):

                print(
                    "⚠️ Gemini 暫時性服務錯誤。"
                )

                print(
                    "➡️ 不等待，立即切換下一把 Key。"
                )

                continue


            # ================================================
            # Timeout / Network
            #
            # 這就是你現在 Key 2 最可能遇到的狀況
            # ================================================

            if (
                error_code is None
                or network_error
            ):

                print(
                    "⚠️ Gemini 發生 Timeout "
                    "或網路連線異常。"
                )

                print(
                    "➡️ 不等待，立即切換下一把 Key。"
                )

                continue


            # ================================================
            # 其他錯誤
            #
            # 例如 400 / 404
            # 換 Key 通常沒有意義
            # ================================================

            print(
                "❌ 發生非備援型錯誤。"
            )

            print(
                "停止 Gemini Key 切換。"
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

    print(
        "\n❌ 所有 Gemini API Key "
        "皆無法成功呼叫。"
    )


    raise RuntimeError(

        "所有 Gemini API Key "
        "目前皆無法成功呼叫。\n"
        f"最後錯誤：{last_error}"

    )