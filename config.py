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
# --- 资金流周报 (Weekly Fund Flow) ---
FUND_FLOW_STEP1 = """
# Role
You are a Financial Data Analyst. Extract content from the Weekly Fund Flows report PDF.

# Task
1. **Extract Meta**: 提取机构名称（如 Goldman Sachs）、分析师姓名、报告日期。
2. **Extract Title**: 识别报告的主标题。注意：主标题通常位于大写的 "WEEKLY FUND FLOWS" 字样之后，是那一行描述性的英文短句（例如 "Robust Bond Flows Year-to-Date"）。
3. **Extract Summary**: 提取正文的第一段话。通常以 "n" 或黑点开头，描述共同基金（mutual funds）的整体情况。
4. **Extract Body**: 提取描述股票（Equity）、固定收益（Fixed Income）及外汇（FX/Cross-border）的具体流动数据段落。

# Output Format (JSON)
{
  "meta": { "institution": "Goldman Sachs", "title_en": "" },
  "raw_content": {
    "summary_text": "",
    "body_text": ""
  }
}
"""

FUND_FLOW_STEP2 = """
# Role
你是一位资深金融翻译专家，专门负责将高盛等投行的周度资金流报告（Weekly Fund Flows）翻译为中文。

# Task
根据提供的 JSON 原始数据，按照以下规则进行翻译和格式化。

# TRANSLATION RULES
1. **Title**: 格式必须为：`【市场动态】` + [翻译 meta.title_en 中的内容]。
2. **Summary**: 仅翻译报告的第一句话。
3. **Terminology Mapping** (必须严格遵守):
   - "Negative flows" -> 资金净流出
   - "Net inflow" -> 净流入
   - "Mainland China" -> 中国大陆
   - "Led by the US" -> 主要由美国...带动
   - "AUM" -> 保持 AUM 不变
   - "sector level" -> 板块层面
   - "Underlying patterns are quite different" -> 资金流分化明显
   - "+" ->录得
4. **Data Style**: 当出现 "Strong inflows" 或具体的资金流入流出数据时，格式改为：`[描述内容] (本周录得XX，前一周为XX)`。请从原文中提取对应数值。

# JSON 填充说明
- **必须填充**: `title`, `Summary`, `body_content`
- **严禁填充 (保持空字符串 "")**: `category`, `Tags`, `Stock`, `rating`, `price_target` 等其他所有 header_info 中的字段。
- **body_content**:不要出现冒号（：），和加减的符号。

# Output Schema (JSON Only)
{
  "header_info": {
    "Category": "",
    "Date": "",
    "Title": "【市场动态】...",
    "Summary": "翻译后的第一段内容...",
    "From": "CIO Office",
    "Tags": "",
    "Recommend Expire Time":"",
    "Language": "Chinese",
    "Stock": "",
    "Stock Rating": "",
    "12m Price Target": "",
    "Related Stock List":"",
    "Related Stock Rating":""

  },
  "body_content": ["段落1：翻译第二段，以截止,,,当周（eg.截至1月14日当周)", "段落2:翻译第三段", "段落3：翻译第四段，开头需要是跨境外汇资金流..."]
}
"""


# --- WSH(Wall Street Highlight) ---
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
        -   If **Equity**: Extract Ticker（must be the US or HK or if both given please give all), Company Name, Rating, Target Price， Previous Target Price (if mentioned).
        -   If **Macro/FX&Commodity**: Ignore Ticker/Rating/TP. Focus on the main economic indicator or asset class.
    -   Extract Thesis Summary & Key Drivers/Catalysts.
     Note the Currency (HKD, USD, RMB, etc.).

# Output Format (JSON)
{{
  "meta": {{ "institution": "", "analyst": "" }},
  "stock": {{ "ticker": "", "name": "", "rating": "", "target_price": ""， "target_price_previous": "","currency": " }},
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
 **Price Target Format:**
    -   MUST include Currency (HKD, USD, RMB).
    -   Nust ensur If a **Previous Target** exists, put it in parentheses: `(Previous Price Target: XX.00)`.if not do not show the Previous Price Target,keep two decimals
    -   If both HKD and USD targets exist, join with `/`.
# STRICT RULES
1.  **Bank Acronyms:** Use Acronyms (JPM, GS, MS, DB, CITICS) in `summary` and `body_content`.
2.  **Grammar:** Treat acronyms as **PLURAL** (e.g., "JPM **expect**").
3. do not show the full bank name in body_content

# Red Highlighting Rule (CRITICAL)
In `body_content`, identify the core viewpoint in EACH paragraph and wrap it with double asterisks `**`.
**THE HIGHLIGHTED SENTENCE MUST FOLLOW THIS EXACT PATTERN:**
* **Pattern:** `**[Acronym] [plural verb] [key insight]...**`
* **Good Examples:**
    * `**JPM maintain their Overweight rating due to strong cash flow.**`
    * `**GS estimate a 20% upside in FY26 earnings.**`
    * `**DB highlight that the valuation is attractive.**`
* **Bad Examples (DO NOT DO THIS):**
    * `**They expect...**` (Do not use 'They' inside `**`)
    * `**The revenue will grow...**` (Must start with the Bank Name)
    * `**JPM expects...**` (Must be plural verb)

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
    "stock": "Ticker string (e.g. 9988.HK / BABA.US) OR Empty",
    "rating": "Rating OR Empty",
    "price_target": "Formatted Price String (e.g. HKD100.00 (Previous Price Target: HKD80.00)),keep two decimals"
  }},
  "body_content": [
    "Paragraph 1: Highlight key sentence with `**`.",
    "Paragraph 2: Highlight key sentence with `**`.",
    ...
    ...
    the key sentence should be their viewpoints, not too loog for key sentences
  ],
  "footer_info": {{
    "stock": "Ticker string (e.g. 9988.HK / BABA.US) OR Empty",
    "rating": "Rating OR Empty",
    "price_target": "Formatted Price String (e.g. HKD100.00(Previous Price Target: HKD80.00)),keep two decimals"
  }}
}}
"""

