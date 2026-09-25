import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors


# =========================================
# 1. 載入 .env
# =========================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env",
    override=True
)


# =========================================
# 2. 讀取新的測試 Key
# =========================================

API_KEY = os.getenv(
    "GEMINI_API_KEY_TEST"
)

print(
    "新 Gemini API Key 是否讀取成功：",
    bool(API_KEY)
)


if not API_KEY:
    raise RuntimeError(
        "找不到 GEMINI_API_KEY_TEST"
    )


# =========================================
# 3. 建立 Gemini Client
# =========================================

client = genai.Client(
    api_key=API_KEY
)


# =========================================
# 4. 發出測試 Request
# =========================================

try:

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input="請只回答：API KEY 測試成功"
    )

    print("\n===== Gemini 回答 =====")

    print(
        interaction.output_text
    )

    print("\n=======================")

    print("✅ 新 API KEY 可以正常使用")


except errors.APIError as exc:

    print("\n❌ Gemini API 發生錯誤")

    print(
        "HTTP / API Code：",
        exc.code
    )

    print(
        "錯誤訊息：",
        exc.message
    )


except Exception as exc:

    print("\n❌ 其他錯誤")

    print(exc)


finally:

    try:
        client.close()
    except Exception:
        pass