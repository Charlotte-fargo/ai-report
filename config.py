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
CLIENT_ID = "cioinsight-api-client"
CLIENT_SECRET = "b02fe9e7-36e6-4c81-a389-9399184eda9b"
# CLIENT_ID = st.secrets["CLIENT_ID"]
# CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
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
        -   If **Equity**: Extract Ticker（must be the US or HK or if both given please give all), Company Name, Rating, Target Price， Previous Target Price (if obviously mentioned).
        -   If **Macro/FX&Commodity**: Ignore Ticker/Rating/TP. Focus on the main economic indicator or asset class.
    -   Extract Thesis Summary & Key Drivers/Catalysts.
     Note the Currency (HKD, USD, RMB, etc.).

# Output Format (JSON) - All content must be in English
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

# USER INSTRUCTION
The report category is defined as: **{category}**.
**Word Count & Structure Rules:**
- The `summary` MUST be strictly between 60 to 70 words. If the category is **Equity**, the summary MUST be exactly 70 words. Check the word count before generating the final output.
- The `body_content` must should be between 500-600 words, consisting of 4-5 paragraphs.
- The `title` should reflect the bank's core viewpoints, not operational updates and should between 7-8 words.

**Price Target Format:**
- MUST include Currency (HKD, USD, RMB).
- If a **Previous Target** exists (if obviously mentioned), put it in parentheses: `(Previous Price Target: XX.00)`. Keep two decimals. If not mentioned, do NOT show the Previous Price Target.
- If both HKD and USD targets exist, join with `/`.

# STRICT RULES
1.  **Bank Acronyms:** Use Acronyms (JPM, GS, MS, DB, CITICS) in `summary` and `body_content`.
2.  **Grammar:** Treat acronyms as **PLURAL** (e.g., "JPM **expect**").
3.  Do not show the full bank name in `body_content`.

# Red Highlighting Rule (CRITICAL)
In `body_content`, identify the core viewpoint in EACH paragraph and wrap it with double asterisks `**`. 

**POSITIONING RULE:** The highlighted sentence must flow NATURALLY within the paragraph. It can be the FIRST, MIDDLE, or LAST sentence. **You MUST vary the position of the highlighted sentence across different paragraphs** so the text reads dynamically and organically, not mechanically. Keep the key sentences concise.

**THE HIGHLIGHTED SENTENCE MUST FOLLOW THIS EXACT PATTERN:**
* **Pattern:** `**[Acronym] [plural verb] [key insight]...**`
* **Good Examples:**
    * `**JPM maintain their Overweight rating due to strong cash flow.**`
    * `**GS estimate a 20% upside in FY26 earnings.**`
    * `**DB highlight that the valuation is attractive.**`
* **Bad Examples (DO NOT DO THIS):**
    * `**They expect...**` (Do not use pronouns like 'They' inside `**`)
    * `**The revenue will grow...**` (Must start with the Bank Name Acronym)
    * `**JPM expects...**` (Must use a plural verb)

# JSON Structure Rules based on Category: **{category}**
-   **If {category} == 'Equity':** You MUST fill in `stock`, `rating`, `price_target`.
-   **If {category} != 'Equity':** You MUST leave `stock`, `rating`, `price_target` as **EMPTY STRINGS** ("").

# Output Schema (JSON Only)
{{
  "header_info": {{
    "category": "Wall Street Highlights-{category}",
    "date": "YYYY/MM/DD",
    "title": "[Full Bank Name]: [Title of the Report] (Must include stock ticker format exactly once, e.g., China Mobile(941.HK))", 
    "summary": "[Acronym] [plural verb]... (Strictly 60-70 words; exactly 70 words if Equity)",
    "tags": "Generate 3 relevant Chinese tags separated by `/` (e.g., 消费/港股/电子)",
    "stock": "Ticker string (e.g. 9988.HK / BABA.US) OR Empty",
    "rating": "Rating OR Empty",
    "price_target": "Formatted Price String (e.g. HKD100.00 (Previous Price Target: HKD80.00)). Only include Previous if mentioned."
  }},
  "body_content": [
    "Paragraph 1 text... **[Acronym] [plural verb] [key insight]...** ...rest of paragraph.",
    "**[Acronym] [plural verb] [key insight]...** ...rest of paragraph 2 text...",
    "...Paragraph 3 text... **[Acronym] [plural verb] [key insight]...**",
    "Paragraph 4 text..."
  ],
  "footer_info": {{
    "stock": "Ticker string (e.g. 9988.HK / BABA.US) OR Empty",
    "rating": "Rating OR Empty",
    "price_target": "Formatted Price String (e.g. HKD100.00(Previous Price Target: HKD80.00)), keep two decimals"
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




