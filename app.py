import os
import time
import json
import re
import requests
import pdfplumber
import streamlit as st
from datetime import datetime
import config  # 引用你现有的配置文件
from doc_generator import DocGenerator

def get_bank_acronym(full_name):
    """
    根据 Step 1 提取的全名，返回对应的缩写
    """
    if not full_name: return "Unknown"
    
    name_upper = full_name.upper()
    
    if "J.P. MORGAN" in name_upper or "JPMORGAN" in name_upper: return "JPM"
    if "GOLDMAN" in name_upper: return "GS"
    if "MORGAN STANLEY" in name_upper: return "MS"
    if "DEUTSCHE" in name_upper: return "DB"
    if "CITIC" in name_upper: return "CITICS"
    if "AMERICA" in name_upper or "BOFA" in name_upper: return "BofA"
    if "UBS" in name_upper: return "UBS"
    if "HSBC" in name_upper: return "HSBC"
    
    # 如果没匹配到，就取前单词作为缩写，去除非法字符
    clean_name = re.sub(r'[^\w]', '', full_name.split()[0])
    return clean_name
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
        -   If **Equity**: Extract Ticker, Company Name, Rating, Target Price， Previous Target Price (if mentioned).
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
    -   Nust ensur If a **Previous Target** exists, put it in parentheses: `(Previous Price Target: XX)`.if not do not show the Previous Price Target
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
    "price_target": "Formatted Price String (e.g. HKD100 (Previous Price Target: HKD80))"
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
    "price_target": "Formatted Price String (e.g. HKD100 (Previous Price Target: HKD80))"
  }}
}}
"""

# ================= 功能函数 =================

def extract_pdf_text(path):
    print(f"📄 正在读取 PDF: {path}...")
    full_text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: full_text += text + "\n"
        return full_text
    except Exception as e:
        print(f"❌ 读取 PDF 失败: {e}")
        return None

def get_token():
    payload = {'grant_type': 'client_credentials', 'client_id': config.CLIENT_ID, 'client_secret': config.CLIENT_SECRET}
    try:
        resp = requests.post(config.AUTH_URL, data=payload, timeout=10)
        resp.raise_for_status()
        return resp.json().get('access_token')
    except Exception as e:
        print(f"❌ Token 获取失败: {e}")
        return None

def call_ai_and_wait_generic(system_prompt, user_content):
    token = get_token()
    if not token: return None

    full_prompt = f"{system_prompt}\n\n=== INPUT DATA ===\n{user_content}"
    url = f"{config.API_BASE_URL}/job"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    payload = {
        "type": "callLlm",
        "metadata": config.API_METADATA,
        "input": {"parameter": {"model_name": config.AI_MODEL_NAME, "prompt": full_prompt}}
    }

    try:
        print(f"🚀 提交 AI 任务...")
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"❌ 提交失败: {resp.text}")
            return None
        
        job_id = resp.json().get("id") or resp.json().get("uuid")
        print(f"⏳ 等待 AI (ID: {job_id})...")

        for i in range(60): 
            time.sleep(2)
            check_url = f"{config.API_BASE_URL}/job/JOB_ID/{job_id}"
            check_resp = requests.get(check_url, headers=headers)
            
            if check_resp.status_code == 200:
                res = check_resp.json()
                status = res.get("status")
                if status in ["SUCCESS", "COMPLETED"]:
                    print("✅ AI 完成！")
                    return clean_json(res.get("output") or res.get("result"))
                elif status == "FAILED":
                    return None
    except Exception as e:
        print(f"❌ 异常: {e}")
        return None

def clean_json(raw_input):
    text = ""
    if isinstance(raw_input, dict):
        text = raw_input.get("content") or raw_input.get("output") or raw_input.get("result")
        if not text:
            if "header_info" in raw_input or "meta" in raw_input: return raw_input
            text = json.dumps(raw_input)
    else:
        text = str(raw_input)

    if text:
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
    
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end != -1:
        try: return json.loads(text[start : end + 1])
        except: pass
    return None

# Streamlit 界面主程序
# ==============================================================================

st.set_page_config(page_title="AI 研报生成器", page_icon="📄")

st.title("📄 AI 智能研报生成器")
st.markdown("上传 PDF -> AI 提取分析 -> 生成标准化 Word 报告")

# --- 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 配置")
    user_name = st.text_input("用户名称 (User Name)", value="Charlotte")
    report_category = st.selectbox(
        "报告类别 (Category)",
        ("Equity", "Macro", "FX&Commodity"),
        index=0
    )
    st.info(f"当前模式: {report_category}\n(Equity 会包含股价评级，其他则隐藏)")

# --- 主界面 ---
uploaded_pdf = st.file_uploader("上传 PDF 研报", type=["pdf"])
uploaded_image = st.file_uploader("上传图表 (可选，将放在文末)", type=["png", "jpg", "jpeg"])

generate_btn = st.button("🚀 开始生成 Word 报告", type="primary")

if generate_btn and uploaded_pdf:
    # 1. 准备工作
    status_box = st.status("正在处理...", expanded=True)
    
    try:
        # A. 读取 PDF
        status_box.write("📄 正在读取 PDF 内容...")
        pdf_text = extract_pdf_text(uploaded_pdf)
        
        if not pdf_text:
            status_box.update(label="❌ PDF 读取失败或为空", state="error")
            st.stop()

        # B. AI Step 1
        status_box.write("🧠 AI Step 1: 正在提取关键数据...")
        prompt_1 = STEP_1_PROMPT_TEMPLATE.format(category=report_category)
        raw_data = call_ai_and_wait_generic(prompt_1, pdf_text)
        
        if not raw_data:
            status_box.update(label="❌ 第一步 AI 分析失败", state="error")
            st.stop()
        
        # C. AI Step 2
        status_box.write("✍️ AI Step 2: 正在进行格式化、缩写和标红...")
        prompt_2 = STEP_2_PROMPT_TEMPLATE.format(category=report_category)
        step1_str = json.dumps(raw_data, indent=2, ensure_ascii=False)
        final_json = call_ai_and_wait_generic(prompt_2, step1_str)
        
        if not final_json:
            status_box.update(label="❌ 第二步 AI 格式化失败", state="error")
            st.stop()

        # D. 后处理 (日期 & 类别)
        today_str = datetime.now().strftime("%Y/%m/%d")
        if "header_info" in final_json:
            final_json["header_info"]["date"] = today_str

        # E. 生成文件名
        # 获取原文件名 (去除后缀)
        original_filename = os.path.splitext(uploaded_pdf.name)[0]
        # 获取银行缩写
        institution = raw_data.get("meta", {}).get("institution", "Unknown")
        bank_acronym = get_bank_acronym(institution)
        # 拼接
        final_filename = f"{report_category}_{user_name}_{bank_acronym}_{original_filename}.docx"
        final_filename = final_filename.replace(" ", "_").replace("/", "-") # 清洗非法字符

        # F. 处理图片
        img_temp_path = None
        if uploaded_image:
            img_temp_path = f"temp_{uploaded_image.name}"
            with open(img_temp_path, "wb") as f:
                f.write(uploaded_image.getbuffer())
            status_box.write(f"🖼️ 已加载图片: {uploaded_image.name}")

        # G. 生成 Word
        status_box.write("💾 正在生成 Word 文档...")
        generator = DocGenerator()
        output_docx_path = f"temp_{final_filename}" # 临时保存
        
        generator.create_styled_doc(final_json, output_docx_path, img_path=img_temp_path)
        
        # H. 完成
        status_box.update(label="✅ 生成成功！", state="complete", expanded=False)
        
        # 显示下载按钮
        with open(output_docx_path, "rb") as f:
            file_bytes = f.read()
            st.download_button(
                label=f"⬇️ 下载报告: {final_filename}",
                data=file_bytes,
                file_name=final_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        # 清理临时文件
        if os.path.exists(output_docx_path): os.remove(output_docx_path)
        if img_temp_path and os.path.exists(img_temp_path): os.remove(img_temp_path)

    except Exception as e:
        status_box.update(label="❌ 发生未知错误", state="error")
        st.error(f"Error details: {e}")

elif generate_btn and not uploaded_pdf:
    st.warning("请先上传 PDF 文件！")








