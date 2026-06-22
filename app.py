import streamlit as st
import requests
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from googlesearch import search
import PyPDF2
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io

st.set_page_config(page_title="B2B精准获客-汽保工具", layout="wide")
st.title("🔧 汽车维修专用工具 · B2B精准客户搜索")

# ==================== 5条产品线（德语版） ====================
PRODUCT_LINES = {
    "1. 空调/冷却系统": {
        "search_terms": [
            "Kühlsystem-Dichtheitsprüfer", "Klimaservice-Werkzeug", "Klimaanlagen-Reparaturwerkzeug",
            "Kältemittel-Füllschlauch", "Klima-Lecksuchgerät"
        ],
        "evidence_keywords": [
            "Kühlsystem-Dichtheitsprüfer", "Klimaservice-Werkzeug", "Klimaanlagen-Reparaturwerkzeug",
            "Kältemittel", "Klima-Lecksuchgerät", "Klimaservice-Station", "Klima-Befüllset"
        ]
    },
    "2. 仪表检测工具": {
        "search_terms": [
            "Zylinderdruckprüfer", "Kraftstoffdruckmessgerät", "Dieseleinspritzung-Tester",
            "Motor-Diagnosegerät", "Unterdruckmanometer", "Abgasgegendruckprüfer"
        ],
        "evidence_keywords": [
            "Zylinderdruckprüfer", "Kraftstoffdruckmessgerät", "Dieseleinspritzung-Tester",
            "Motor-Diagnosegerät", "Unterdruckmanometer", "Abgasgegendruckprüfer",
            "Kompressionstester", "Einspritzdüsen-Tester"
        ]
    },
    "3. 刹车/底盘/结构": {
        "search_terms": [
            "Bremskolbenrückstellsatz", "Fahrwerk-Reparaturwerkzeug", "Kugelgelenkabzieher",
            "Kupplungszentrierwerkzeug", "Radlager-Abzieher-Set", "Stoßdämpfer-Montagewerkzeug"
        ],
        "evidence_keywords": [
            "Bremskolbenrückstellsatz", "Fahrwerk-Reparaturwerkzeug", "Kugelgelenkabzieher",
            "Kupplungszentrierwerkzeug", "Radlager-Abzieher", "Stoßdämpfer-Montagewerkzeug",
            "Bremsen-Reparaturset", "Querlenker-Abzieher"
        ]
    },
    "4. 液体更换/系统维护": {
        "search_terms": [
            "Bremsenentlüftungsgerät", "Kühlmittel-Befüllset", "Bremsflüssigkeitswechsler",
            "Kältemittelöl-Einfüllwerkzeug", "Absaug- und Einfüllspritze"
        ],
        "evidence_keywords": [
            "Bremsenentlüftungsgerät", "Kühlmittel-Befüllset", "Bremsflüssigkeitswechsler",
            "Kältemittelöl-Einfüllwerkzeug", "Absaugspritze", "Befüllset", "Entlüftungsgerät"
        ]
    },
    "5. 内饰撬棒/卡扣耗材": {
        "search_terms": [
            "Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set", "Innenraum-Demontagewerkzeug",
            "Öldichtungs-Haken-Set", "Schlauchklemmen-Zangen-Set"
        ],
        "evidence_keywords": [
            "Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set", "Innenraum-Demontagewerkzeug",
            "Öldichtungs-Haken-Set", "Schlauchklemmen-Zangen-Set", "Verkleidungs-Clip",
            "Türverkleidungswerkzeug"
        ]
    }
}

ROLE_WORDS = ["Großhandel", "Großhändler", "Importeur", "Import", "Distributor", "Händler", "Lieferant", "Fachhandel"]
EXCLUDE_WORDS = [
    "Werkstatt", "Reparatur", "Service-Center", "Autohaus", "Reifenservice",
    "Karosseriebau", "Lackiererei", "Tuning", "Industrie", "Baumaschinen",
    "Gartengeräte", "Landwirtschaft", "Baustoffe", "Maler", "Bauunternehmen"
]

# ==================== PDF 图片预览函数 ====================
def render_pdf_previews(pdf_file):
    """将PDF每一页转为缩略图，返回图片列表"""
    try:
        pdf_file.seek(0)
        images = convert_from_bytes(pdf_file.read(), dpi=150)  # 低分辨率，快速预览
        return images
    except:
        return None

def ocr_from_images(images):
    """对多张图片进行OCR，返回合并文本"""
    try:
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img, lang='eng+chi_sim+deu') + "\n"
        return text.strip()
    except:
        return "OCR失败"

# ==================== 其他辅助函数（同前，略） ====================
def fetch_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=10, headers=headers)
        resp.raise_for_status()
        return resp.text
    except:
        return None

def contains_any(text, kw_list):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in kw_list)

def extract_lead(html, url, evidence_keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()

    if contains_any(text, EXCLUDE_WORDS):
        return None
    if not contains_any(text, ROLE_WORDS):
        return None
    if not contains_any(text, evidence_keywords):
        return None

    domain = urlparse(url).netloc
    company = soup.title.string.strip() if soup.title else domain

    emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
    emails = [e for e in emails if 'noreply' not in e and 'example' not in e]

    socials = []
    linkedin = re.findall(r'(https?://[a-z]+\.linkedin\.com/company/[^"\'\s]+)', html)
    if linkedin:
        socials.append(("LinkedIn", linkedin[0]))
    facebook = re.findall(r'(https?://[a-z]+\.facebook\.com/[^"\'\s]+)', html)
    if facebook:
        socials.append(("Facebook", facebook[0]))
    instagram = re.findall(r'(https?://[a-z]+\.instagram\.com/[^"\'\s]+)', html)
    if instagram:
        socials.append(("Instagram", instagram[0]))
    if not socials:
        socials.append(("", "未找到公开社媒"))

    scale = "中小型"

    ecommerce = []
    if 'amazon' in html:
        ecommerce.append("Amazon")
    if 'ebay' in html:
        ecommerce.append("eBay")
    ecommerce_str = ", ".join(ecommerce) if ecommerce else "未发现"

    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    contact = "邮箱: " + (", ".join(emails) if emails else "无") + "; 电话: " + (phones[0] if phones else "官网表单")

    matched = [kw for kw in evidence_keywords if kw.lower() in text.lower()]

    return {
        '公司名称': company,
        '官网': url,
        '匹配产品': ', '.join(matched[:3]),
        '社媒': socials,
        '规模': scale,
        '电商渠道': ecommerce_str,
        '联系方式': contact,
    }

# ==================== 主界面 ====================
with st.sidebar:
    st.header("⚙️ 搜索配置")

    # 选择产品线
    selected_lines = []
    st.subheader("勾选要搜索的产品线（至少选一个）")
    for line_name, data in PRODUCT_LINES.items():
        if st.checkbox(line_name, value=True):
            selected_lines.append((line_name, data))

    # 城市输入（德国主要城市）
    cities_str = st.text_area("搜索城市（每行一个）", "Berlin\nHamburg\nMünchen\nFrankfurt\nStuttgart")
    cities = [c.strip() for c in cities_str.splitlines() if c.strip()]

    # PDF上传（可选）
    pdf_file = st.file_uploader("📄 上传产品目录PDF（可选，辅助确认关键词）", type=["pdf"])
    manual_keywords_override = ""
    if pdf_file:
        with st.expander("📷 查看PDF页面（点击展开）"):
            images = render_pdf_previews(pdf_file)
            if images:
                # 显示每页缩略图
                for i, img in enumerate(images):
                    st.image(img, caption=f"第 {i+1} 页", width=300)
                # OCR提取文字供参考
                ocr_text = ocr_from_images(images)
                st.text_area("OCR提取的文字（供参考，可复制修正）", value=ocr_text, height=150)
            else:
                st.error("PDF渲染失败，请确认文件有效。")
        # 允许手动输入关键词（覆盖产品线）
        manual_keywords_override = st.text_area(
            "📝 手动输入搜索关键词（每行一个，将覆盖产品线选择）",
            value="",
            placeholder="例如：Bremskolbenrückstellsatz\nZylinderdruckprüfer",
            height=100
        )

    st.markdown("---")
    st.caption("程序将组合：关键词 + 经销商角色 + 城市 进行搜索")

# ==================== 开始搜索 ====================
if st.button("🚀 开始精准搜索", type="primary"):
    if not selected_lines and not manual_keywords_override.strip():
        st.error("请至少勾选一条产品线，或手动输入关键词。")
    elif not cities:
        st.error("请至少填写一个城市。")
    else:
        # 构建搜索关键词
        if manual_keywords_override.strip():
            search_keywords = [k.strip() for k in manual_keywords_override.splitlines() if k.strip()]
        else:
            search_keywords = []
            for line_name, data in selected_lines:
                search_keywords.extend(data['search_terms'])

        # 每个产品线对应的证据关键词（用于验证）
        if manual_keywords_override.strip():
            # 如果手动输入，使用所有产品线的证据词合并
            evidence_keywords = []
            for data in PRODUCT_LINES.values():
                evidence_keywords.extend(data['evidence_keywords'])
        else:
            evidence_keywords = []
            for line_name, data in selected_lines:
                evidence_keywords.extend(data['evidence_keywords'])

        # 生成所有查询
        queries = []
        for kw in search_keywords:
            for role in random.sample(ROLE_WORDS, min(2, len(ROLE_WORDS))):
                for city in cities:
                    queries.append(f"{kw} {role} {city}")

        st.info(f"将执行 {len(queries)} 组搜索...")

        all_leads = []
        seen = set()
        progress = st.progress(0)
        status = st.empty()

        for i, q in enumerate(queries):
            status.text(f"搜索: {q}")
            progress.progress((i+1)/len(queries))
            try:
                results = search(q, num=5, stop=5, user_agent='Mozilla/5.0', lang='de', country='de')
            except:
                time.sleep(2)
                continue

            for url in results:
                domain = urlparse(url).netloc
                if domain in seen:
                    continue
                seen.add(domain)
                html = fetch_page(url)
                if not html:
                    continue
                lead = extract_lead(html, url, evidence_keywords)
                if lead:
                    all_leads.append(lead)
                time.sleep(random.uniform(2, 5))
            time.sleep(3)

        progress.empty()
        status.empty()

        if not all_leads:
            st.warning("未找到匹配公司，请尝试减少城市或放宽关键词。")
        else:
            unique = []
            names = set()
            for l in all_leads:
                if l['公司名称'] not in names:
                    names.add(l['公司名称'])
                    unique.append(l)
            final = unique[:5]

            st.success(f"找到 {len(unique)} 家匹配公司，展示前5家。")
            for i, lead in enumerate(final, 1):
                with st.container():
                    st.subheader(f"{i}. {lead['公司名称']}")
                    st.markdown(f"🌐 官网: [{lead['官网']}]({lead['官网']})")
                    social_links = []
                    for name, link in lead['社媒']:
                        if name and link.startswith('http'):
                            social_links.append(f"[{name}]({link})")
                        else:
                            social_links.append(link)
                    st.markdown(f"📱 社媒: {' · '.join(social_links)}")
                    st.markdown(f"🔧 匹配产品: {lead['匹配产品']}")
                    st.markdown(f"🏢 规模: {lead['规模']}  |  🛒 电商: {lead['电商渠道']}")
                    st.markdown(f"📞 联系方式: {lead['联系方式']}")
                    st.markdown("---")

            df = pd.DataFrame(final)
            df['社媒'] = df['社媒'].apply(lambda x: '; '.join([f"{n}: {l}" for n,l in x]) if isinstance(x, list) else x)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载结果 CSV", csv, "leads.csv", "text/csv")
