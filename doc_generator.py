import re
from docx import Document
from docx.shared import Pt, RGBColor, Inches 
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
import os
# 🔥 1. 设置您指定的红色 (RGB: 192, 0, 0)
CUSTOM_RED = RGBColor(192, 0, 0) 

class DocGenerator:
    def create_styled_doc(self, json_data, output_path="Output.docx",img_path = None):
        if not json_data:
            print("❌ 数据为空，无法生成")
            return

        doc = Document()
        
        # --- 基础字体设置 ---
        style = doc.styles['Normal']
        style.font.name = 'DengXian'
        style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑') # 中文用微软雅黑
        style.font.size = Pt(11)

        # --- 辅助函数：应用段落排版 (两端对齐 + 1.07倍行距) ---
        def apply_paragraph_style(paragraph, align_justify=False):
            pf = paragraph.paragraph_format
            if align_justify:
                pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            else:
                pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf.space_before = Pt(12)
            pf.space_after = Pt(0)
            pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            pf.line_spacing = 1.07

        # --- 🔥 核心函数：智能解析并标红重点句 ---
        def add_paragraph_with_highlight(document, text):
            p = document.add_paragraph()
            apply_paragraph_style(p, align_justify=True) # 正文两端对齐
            
            # 使用正则切分：保留分隔符 **...**
            # 例如: "普通文字 **重点句** 普通文字" -> ['普通文字 ', '**重点句**', ' 普通文字']
            segments = re.split(r'(\*\*.*?\*\*)', str(text))
            
            for seg in segments:
                if not seg: continue
                
                # 检查是否是被 ** 包裹的重点句
                if seg.startswith('**') and seg.endswith('**'):
                    clean_text = seg[2:-2] # 去掉星号
                    run = p.add_run(clean_text)
                    run.font.color.rgb = CUSTOM_RED # 🔴 变为指定的红色
                    # run.font.bold = True # 如果希望红字同时加粗，请取消此行注释
                else:
                    # 普通文字：黑色
                    run = p.add_run(seg)
                    run.font.color.rgb = RGBColor(0, 0, 0)

        # --- 1. 顶部信息 (Header) ---
        header = json_data.get("header_info", {})
        header_mapping = [
            ("Category", "category"), ("Date", "date"), ("Title", "title"),
            ("Summary", "summary"), ("Tags", "tags"), ("Stock", "stock"),
            ("Stock Rating", "rating"), ("12m Price Target", "price_target")
        ]

        for label, key in header_mapping:
            val = header.get(key, "")
            if val:
                p = doc.add_paragraph()
                apply_paragraph_style(p, align_justify=False)
                # 标签部分
                run = p.add_run(f"#{label}# ")
                run.font.bold = True
                # 数值部分
                run_val = p.add_run(str(val))
                run_val.font.bold = True # Header部分全部加粗

        # --- 2. 正文 (Body Content) - 支持句内标红 ---
        # 写入 #Content# 标签
        p = doc.add_paragraph()
        apply_paragraph_style(p, align_justify=False)
        run = p.add_run("#Content#")
        run.font.bold = True
        
        body_list = json_data.get("body_content", [])
        
        # 容错处理：如果 AI 返回的是字符串而不是列表
        if isinstance(body_list, str):
            body_list = [x for x in body_list.split('\n') if x.strip()]

        if isinstance(body_list, list):
            for paragraph_text in body_list:
                # 🔥 调用高亮函数写入每一段
                add_paragraph_with_highlight(doc, paragraph_text)

        # --- 3. 底部信息 (Footer) - 全红 ---
        footer = json_data.get("footer_info", {})
        if footer:
            footer_items = [
                ("Stock", footer.get("stock", "")),
                ("Stock Rating", footer.get("rating", "")),
                ("12m Price Target", footer.get("price_target", ""))
            ]
            for label, val in footer_items:
                if val:
                    p = doc.add_paragraph(f"{label}: {val}")
                    apply_paragraph_style(p, align_justify=False)
                    for run in p.runs:
                        run.font.bold = True
                        run.font.color.rgb = CUSTOM_RED # 🔴 底部也用同一个红色
                    # 🔥🔥🔥 [新增功能] 4. 插入文末图片 🔥🔥🔥
        # ==========================================
        # 检查：用户是否提供了路径，且路径下的文件是否真的存在
        if img_path and os.path.exists(img_path):
            print(f"🖼️ 检测到图片，正在插入文末: {img_path}")
            
            # 创建一个新段落用于放图片
            img_p = doc.add_paragraph()
            # 关键：设置居中对齐
            img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER 
            # 增加一点段前距，让图片和上面的文字拉开距离
            img_p.paragraph_format.space_before = Pt(24) 
            
            run = img_p.add_run()
            # 插入图片，并限制宽度为 6 英寸（根据需要调整），高度自动按比例缩放
            run.add_picture(img_path, width=Inches(6.0))

        try:
            doc.save(output_path)
            print(f"✅ 文档已生成: {output_path}")
        except Exception as e:
            print(f"❌ 保存失败: {e}")

        try:
            doc.save(output_path)
            print(f"✅ 文档生成成功 (包含标红重点): {output_path}")
        except Exception as e:
            print(f"❌ 保存失败: {e}")