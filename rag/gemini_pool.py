import os

from google import genai
from google.genai import errors


# ============================================================
# 1. 讀取 Gemini API Keys
# ============================================================

GEMINI_API_KEYS = []

for i in range(1, 11):

    key = os.getenv(
        f"GEMINI_API_KEY_{i}"
    )

    if key:
        GEMINI_API_KEYS.append(key)


# 向下相容舊的 GEMINI_API_KEY
old_key = os.getenv("GEMINI_API_KEY")

if old_key and old_key not in GEMINI_API_KEYS:
    GEMINI_API_KEYS.append(old_key)


if not GEMINI_API_KEYS:

    raise RuntimeError(
        "找不到任何 Gemini API Key。"
    )


# ============================================================
# 2. Gemini API Key Pool
# ============================================================

def create_gemini_interaction(
    prompt: str,
    model: str = "gemini-3.6-flash"
):

    last_error = None

    for index, api_key in enumerate(
        GEMINI_API_KEYS
    ):

        print(
            f"嘗試 Gemini API Key "
            f"{index + 1}/{len(GEMINI_API_KEYS)}"
        )

        client = genai.Client(
            api_key=api_key
        )

        try:

            interaction = (
                client
                .interactions
                .create(
                    model=model,
                    input=prompt
                )
            )

            print(
                f"Gemini API Key "
                f"{index + 1} 呼叫成功"
            )

            return interaction

        except errors.APIError as exc:

            last_error = exc

            print(
                f"Gemini API Key "
                f"{index + 1} 發生 API Error："
                f"{exc.code} - {exc.message}"
            )

            # ----------------------------------------
            # 429 = Rate Limit / Quota Exhausted
            # ----------------------------------------

            if exc.code == 429:

                print(
                    f"Key {index + 1} "
                    f"目前受到 Rate Limit，"
                    f"嘗試下一個 Key..."
                )

                continue

            # ----------------------------------------
            # 401 / 403
            # Key 無效或權限問題
            # ----------------------------------------

            elif exc.code in (401, 403):

                print(
                    f"Key {index + 1} "
                    f"驗證或權限失敗，"
                    f"嘗試下一個 Key..."
                )

                continue

            # 其他錯誤不要亂換 Key
            else:

                raise

        finally:

            try:
                client.close()

            except Exception:
                pass


    # 所有 Key 都失敗
    raise RuntimeError(
        "所有 Gemini API Key 目前皆無法使用。"
        f"最後錯誤：{last_error}"
    )