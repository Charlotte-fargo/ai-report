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

# --- WSH(Wall Street Highlight) ---
# 步骤 1: 分析师
STEP_1_PROMPT_TEMPLATE = config.STEP_1_PROMPT_TEMPLATE

# 步骤 2: 编辑
STEP_2_PROMPT_TEMPLATE = config.STEP_2_PROMPT_TEMPLATE

# --- 资金流周报 (Weekly Fund Flow) ---
FUND_FLOW_STEP1 = config.FUND_FLOW_STEP1
FUND_FLOW_STEP2 = config.FUND_FLOW_STEP2

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
        ("Equity", "Macro", "FX&Commodity","Weekly Fund Flow"),
        index=0
    )
    st.info(f"当前模式: {report_category}\n(Equity 会包含股价评级，其他则隐藏)")

# --- 主界面 ---
uploaded_pdf = st.file_uploader("上传 PDF 研报", type=["pdf"])
# 逻辑分支：图片上传控件
uploaded_image_manual = None
if report_category == "Weekly Fund Flow":
    st.caption("✅ 资金流模式。")
else:
    uploaded_image_manual = st.file_uploader("上传封面图 (可选)", type=["png", "jpg", "jpeg"])

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
        if report_category == "Weekly Fund Flow":
            # === A. 资金流模式 ===
            status_box.write("🔍 Step 1: 提取资金流数据...")
            raw_data = call_ai_and_wait_generic(FUND_FLOW_STEP1, pdf_text)
            if not raw_data: 
                status_box.update(label="❌ Step 1 失败", state="error")
                st.stop()
            
            status_box.write("✍️ Step 2: 执行【市场动态】翻译标准...")
            final_json = call_ai_and_wait_generic(FUND_FLOW_STEP2, json.dumps(raw_data))
            print(final_json)
            if report_category == "Weekly Fund Flow":
            # 强制二次确认：除了指定的三个字段，其余全部清空或保持原样
                allowed_keys = ["title", "summary", "body_content", "date", "from", "language"]
                header = final_json.get("header_info", {})
                for key in header.keys():
                    if key.lower() not in allowed_keys:
                        header[key] = "" # 确保不属于 fund flow 的字段绝对为空
            
            # 构造文件名 (资金流通常用机构名或固定格式)
            bank_acronym = "GS" # 默认为高盛，或者从 raw_data 里提取
            final_filename = f"WeeklyFlow_{user_name}_{bank_acronym}_{datetime.now().strftime('%Y%m%d')}.docx"
            if not final_json:
                status_box.update(label="❌ AI 生成失败", state="error")
                st.stop()

            # 3. 后处理与生成文档
            today_str = datetime.now().strftime("%Y/%m/%d")
            if "header_info" in final_json:
                final_json["header_info"]["date"] = today_str

            status_box.write("💾 正在生成 Word 文档...")
            generator = DocGenerator()
            output_docx_path = f"temp_{final_filename}"
            
            # 关键：调用 create_styled_doc，传入 image_list (注意：DocGenerator 必须支持 image_list 参数)
            # 如果你没改 DocGenerator，请确保它的 create_styled_doc 接收 image_list=extracted_images
            generator.create_styled_doc(final_json, output_docx_path, img_path=None,report_category=report_category)
            
            status_box.update(label="✅ 生成成功！", state="complete", expanded=False)
        else:
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
            # 手动图片处理
            temp_img_path = None
            if uploaded_image_manual:
                temp_img_path = f"temp_{uploaded_image_manual.name}"
                with open(temp_img_path, "wb") as f:
                    f.write(uploaded_image_manual.getbuffer())
                extracted_images = [temp_img_path] # 放入列表
                status_box.write(f"🖼️ 已加载封面图: {uploaded_image_manual.name}")

            # G. 生成 Word
            status_box.write("💾 正在生成 Word 文档...")
            generator = DocGenerator()
            output_docx_path = f"temp_{final_filename}" # 临时保存
            
            generator.create_styled_doc(final_json, output_docx_path, img_path=temp_img_path，report_category=report_category)
            
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
        if temp_img_path and os.path.exists(temp_img_path): os.remove(temp_img_path)

    except Exception as e:
        status_box.update(label="❌ 发生未知错误", state="error")
        st.error(f"Error details: {e}")

elif generate_btn and not uploaded_pdf:
    st.warning("请先上传 PDF 文件！")











