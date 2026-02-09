# config.py
from pptx.dml.color import RGBColor
import requests
import os
from dotenv import load_dotenv
import streamlit as st
# ==============================================================================
# 加载 .env 文件中的变量
load_dotenv()

# ==============================================================================
# Web 界面访问密码
# APP_PASSWORD = os.getenv("APP_PASSWORD", "123456")

# 1. AI API 与 认证配置
# ==============================================================================

AUTH_URL = "https://auth-v2.easyview.xyz/realms/evhk/protocol/openid-connect/token"
API_BASE_URL = "https://api-v2.easyview.xyz/v3/ai"
# AI 服务的专用凭据
# CLIENT_ID = "cioinsight-api-client"
# CLIENT_SECRET = "b02fe9e7-36e6-4c81-a389-9399184eda9b"
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
# AI 模型名称
AI_MODEL_NAME = "deepseek-r1"

# 请求元数据 (Metadata)
API_METADATA = {
    "tenantId": "GOLDHORSE",
    "clientId": "CIO",
    "userId": "script_runner",
    "priority": 1,
    "custom": {}
}
# 获取访问令牌的函数
def get_access_token_b(CLIENT_ID, CLIENT_SECRET):
    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    try:
        resp = requests.post(AUTH_URL, data=payload)
        resp.raise_for_status()
        return resp.json().get('access_token')
    except Exception as e:
        print(f" 认证失败: {e}")
        return None
API_TOKEN = get_access_token_b(CLIENT_ID, CLIENT_SECRET)
# ==============================================================================
# 2. AI 提示词 (Prompt) 配置 - 决定报告质量的核心
# 步骤 1: 分析师 (只负责提取数据，不关心格式)
STEP_1_PROMPT = """
# Role
You are a Senior Financial Analyst. Your job is to extract raw data from the provided OCR text.
Do NOT summarize or rewrite yet; just extract the facts accurately.

# Input
Raw OCR text from a PDF.

# Task
Extract the following specific data points.
1. Institution Name (e.g., J.P. Morgan)
2. Report Date
3. Stock Ticker & Name
4. Rating (e.g., Overweight) & Target Price
5. Summary of the Investment Thesis
6. Key Drivers / Catalysts
8. Financial Outlook (Revenue/EPS forecasts)

# Output Format (JSON)
{
  "meta": { "institution": "", "date": "", "analyst": "" },
  "stock": { "ticker": "", "name": "", "rating": "", "target_price": "" },
  "content_raw": {
    "thesis_summary": "...",
    "drivers": ["...", "..."],
    "financial_outlook": "..."
  }
}
"""

# 步骤 2: 编辑 (只负责格式化、缩写、标红)
STEP_2_PROMPT = """
# Role
You are a Strict Financial Editor. You will receive structured data extracted from a report.
Your ONLY job is to reformat this data into a specific JSON schema for a document generator.
body_content should between 400-500 words

# STRICT RULES (Must Follow)
1.  **Bank Acronyms:** -   Convert Full Names to Acronyms in `summary` and `body_content`:
    -   J.P. Morgan -> **JPM** | Goldman Sachs -> **GS** | Morgan Stanley -> **MS** | Deutsche Bank -> **DB** | CITIC -> **CITICS**
2.  **Grammar:** -   Treat acronyms as **PLURAL**. (e.g., "JPM **expect**", "GS **are**").
    -   Narrative style: "[Acronym] [verb] that..."
3.  **Red Highlighting (CRITICAL):**
    -   In `body_content`, rewrite the raw data into flowing paragraphs.
    -   **ACTION:** In EACH paragraph, identify the most important sentence and wrap it with double asterisks `**`.
    -   Example: "GS note that **revenue grew by 20% YoY due to cloud demand.**"

# Output Schema (JSON Only)
{
  "header_info": {
    "category": "Wall Street Highlights-Equity",
    "date": "YYYY/MM/DD",
    "title": "[Full Bank Name]: [Company Name]精炼的英文标题，体现报告的核心观点", 
    "summary": "[Acronym] [plural verb]... (max 60 words)",
    "tags": "Generate 3 relevant Chinese tags separated by `/` (e.g., 消费/港股/电子)",
    "stock": "Ticker",
    "rating": "Rating",
    "price_target": "Price"
  },
  "body_content": [
    "Paragraph 1 (Core View): Start with '[Acronym] [plural verb]...'. Highlight key sentence with `**`.",
    "Paragraph 2 (Drivers/Catalysts): Combine drivers into a paragraph. Highlight key sentence with `**`.",
    "Paragraph 3 (Financials/Valuation): Discuss numbers. Highlight key sentence with `**`."
  ],
  "footer_info": {
    "stock": "Ticker",
    "rating": "Rating",
    "price_target": "Price"
  }
}
"""
