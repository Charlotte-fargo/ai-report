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
# 摘要生成专用模型（中文内容生成）
SUMMARY_MODEL_NAME = "gemini-3-pro-preview"

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
# 步骤 1: 分析师
STEP_1_PROMPT_TEMPLATE = """
# Role
You are a Senior Financial Analyst. Extract raw data from the provided OCR text.

# USER INSTRUCTION
The user has defined this report category as: **{category}**.

# Task
1.  **Extract Meta Data:** Institution Name, Analyst Name.
2.  **Extract Core Content based on Category:**
    -   **Since this is {category}:**
        -   If **Equity**: Extract Ticker, Company Name, Rating, Target Price.
        -   If **Macro/FX/Commodity**: Ignore Ticker/Rating/TP. Focus on the main economic indicator or asset class.
    -   Extract Thesis Summary & Key Drivers/Catalysts.

# Output Format (JSON)
{{
  "meta": {{ "institution": "", "analyst": "" }},
  "stock": {{ "ticker": "", "name": "", "rating": "", "target_price": "" }},
  "content_raw": {{
    "thesis_summary": "...",
    "drivers": ["...", "..."],
    "financial_outlook": "..."
  }}
}}
"""

# 步骤 2: 编辑
STEP_2_PROMPT_TEMPLATE = """
# Role
You are a Strict Financial Editor. Reformat extracted data into a specific JSON schema.
body_content should between 400-500 words, and including 4-5 paragraphs
# USER INSTRUCTION
The report category is defined as: **{category}**.

# STRICT RULES
1.  **Bank Acronyms:** Use Acronyms (JPM, GS, MS, DB, CITICS) in `summary` and `body_content`.
2.  **Grammar:** Treat acronyms as **PLURAL** (e.g., "JPM **expect**").
3.  **Red Highlighting (CRITICAL):**
    -   In `body_content`, identify the most important sentence in EACH paragraph and wrap it with double asterisks `**`.

# JSON Structure Rules based on Category: **{category}**
-   **If {category} == 'Equity':** You MUST fill in `stock`, `rating`, `price_target`.
-   **If {category} != 'Equity':** You MUST leave `stock`, `rating`, `price_target` as **EMPTY STRINGS** ("").

# Output Schema (JSON Only)
{{
  "header_info": {{
    "category": "Wall Street Highlights-{category}",
    "date": "YYYY/MM/DD",
    "title": "[Full Bank Name]: [Title of the Report]should including stock(ticker.country for example,China Mobile(941.HK) )", 
    "summary": "[Acronym] [plural verb]... (max 60 words)",
    "tags": "Generate 3 relevant Chinese tags separated by `/` (e.g., 消费/港股/电子)",
    "stock": "Ticker OR Empty",
    "rating": "Rating OR Empty",
    "price_target": "Price OR Empty"
  }},
  "body_content": [
    "Paragraph 1: Highlight key sentence with `**`.",
    "Paragraph 2: Highlight key sentence with `**`.",
    ...
    ...
  ],
  "footer_info": {{
    "stock": "Ticker OR Empty",
    "rating": "Rating OR Empty",
    "price_target": "Price OR Empty"
  }}
}}
"""

STEP_3_PROMPT = """
# Role
You are a Professional Chinese Financial Content Curator. Your task is to transform research reports into concise, publication-ready Chinese content with elegant formatting suitable for financial social media.

# Input
Structured report data including Report Filename, Institution name, Stock details, Rating, Core investment thesis.
User will also provide a Report Link ID.

# Task
任务：根据投行研究报告的文本和文件名，提取核心观点，并按要求输出 JSON 格式的摘要。

# Strict Rules
1. 标题基本格式：【投行中文名字：精炼核心标题】
2. 股票代码位置与防屏蔽（CRITICAL）：
   - 如果是**个股报告**，股票代码必须**紧贴在公司名称的正后方**。
   - 格式必须为：公司名（代码[ZWSP].国家/地区）。
   - **多代码处理（重要）**：如果报告中包含该公司的多个股票代码（例如同时有 A股 和 H股），**必须将它们全部列出，用 " / " 分隔**。
   - 必须在**每一个**代码与后缀之间的点号（.）前面插入零宽空格（Unicode: U+200B）。在 JSON 中请直接输出转义符 `\u200B`。
4. 内容预览：提供 120-150 字的观点总结。直接切入核心逻辑，语言仿《华尔街日报》。
5. 链接生成：使用提供的 Report Link ID 替换 `{provided_id}`。

# NEGATIVE EXAMPLES (反面案例)
❌ 反面案例 1（代码位置错误，跑到了标题最后）：
"title": "【德意志银行：比亚迪2月销量受假期拖累，海外市场尽显韧性 (1211\u200B.HK)】"

❌ 反面案例 2（宏观报告乱加代码）：
"title": "【高盛：美联储降息预期升温 (Macro\u200B.US)】"

❌ 反面案例 3（漏掉多地上市代码，或漏加零宽空格）：
"title": "【里昂证券：宁德时代 (300750.SZ/3750\u200B.HK) 储能业务超预期增长】"
👉 原因：300750 后面漏了 `\u200B`。

# POSITIVE EXAMPLES (正确示范)
[
  {
    "description": "单代码个股报告",
    "output": {
      "title": "【摩根大通：昆仑能源 (135\u200B.HK) 受中东局势影响有限，为行业首选】",
      "preview": "摩根大通研究报告指出...",
      "link": "https://news.fargowealth.com/?id=38605&feature=1&viewChannelId=4&rootOrgId=1"
    }
  },
  {
    "description": "多代码双重上市个股报告（每个代码都有零宽空格）",
    "output": {
      "title": "【里昂证券：宁德时代 (300750\u200B.SZ / 3750\u200B.HK) 储能业务超预期增长，估值吸引力凸显】",
      "preview": "里昂证券发布报告...",
      "link": "https://news.fargowealth.com/?id=38606&feature=1&viewChannelId=4&rootOrgId=1"
    }
  },
  {
    "description": "宏观报告，完全不包含代码",
    "output": {
      "title": "【高盛：美联储降息预期升温，全球资金回流新兴市场】",
      "preview": "高盛发布最新宏观研报指出...",
      "link": "https://news.fargowealth.com/?id=38607&feature=1&viewChannelId=4&rootOrgId=1"
    }
  }
]

# Output Format (JSON ONLY)
必须严格输出合法的 JSON 格式，不要包含任何 markdown 代码块标记（如 ```json），格式如下：
{
  "title": "【投行名：包含 公司名 (代码1\u200B.地区 / 代码2\u200B.地区) 的标题】 或 【投行名：无代码的宏观标题】",
  "preview": "120-150字的专业中文摘要...",
  "link": "[https://news.fargowealth.com/?id=](https://news.fargowealth.com/?id=){provided_id}&feature=1&viewChannelId=4&rootOrgId=1"
}
"""

