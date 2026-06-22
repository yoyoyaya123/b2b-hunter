import streamlit as st
import requests
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from googlesearch import search

st.set_page_config(page_title="B2B智能搜客·多语言版", layout="wide")
st.title("🔧 汽车维修专用工具 · 智能客户搜索系统")

# ========== 内置多语言支持 ==========
LANGUAGES = {
    "德国": {
        "lang_code": "de",
        "country_code": "de",
        "role_words": ["Großhandel", "Großhändler", "Importeur", "Import", "Distributor", "Händler", "Lieferant", "Fachhandel", "Wiederverkäufer"],
        "exclude_words": ["Werkstatt", "Reparatur", "Service-Center", "Autohaus", "Reifenservice", "Karosseriebau", "Lackiererei", "Tuning", "Industrie", "Baumaschinen", "Gartengeräte", "Landwirtschaft"],
        "evidence_keywords": ["Bremskolbenrückstellsatz", "Zylinderdruckprüfer", "Klimaservice-Werkzeug", "Bremsenentlüftungsgerät", "Kraftstoffdruckmessgerät", "Kühlsystem-Dichtheitsprüfer", "Dieseleinspritzung-Tester", "Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set", "Kugelgelenkabzieher", "Kupplungszentrierwerkzeug", "Bremsflüssigkeitswechsler"],
        "cities": ["Berlin", "Hamburg", "München", "Frankfurt", "Stuttgart", "Köln", "Düsseldorf"],
        "scale_small": ["Familienbetrieb", "Inhabergeführt", "mittelständisch"]
    },
    "法国": {
        "lang_code": "fr",
        "country_code": "fr",
        "role_words": ["grossiste", "importateur", "distributeur", "fournisseur", "revendeur", "commerce de gros"],
        "exclude_words": ["garage", "atelier de réparation", "carrosserie", "peinture", "pneumatique", "industriel", "bâtiment", "jardinage", "agricole"],
        "evidence_keywords": [
            "outil de climatisation auto", "détecteur de fuite de radiateur", "manifold frigorifique",
            "testeur de compression", "manomètre de pression d'essence", "testeur d'injecteur diesel",
            "kit de repose-culasse", "extracteur de rotule", "démonte-amortisseur", "purgeur de frein",
            "remplisseur de liquide de refroidissement", "kit de leviers en nylon", "kit de clips auto"
        ],
        "cities": ["Paris", "Lyon", "Marseille", "Lille", "Bordeaux", "Toulouse", "Nantes"],
        "scale_small": ["familiale", "dirigée par son fondateur", "PME"]
    },
    "西班牙": {
        "lang_code": "es",
        "country_code": "es",
        "role_words": ["mayorista", "importador", "distribuidor", "proveedor", "comercio al por mayor"],
        "exclude_words": ["taller", "reparación", "carrocería", "pintura", "neumáticos", "industrial", "construcción", "jardinería", "agrícola"],
        "evidence_keywords": [
            "herramienta de climatización", "probador de fugas de radiador", "manómetro de refrigerante",
            "comprobador de compresión", "manómetro de presión de combustible", "probador de inyectores diésel",
            "juego de retroceso de freno", "extractor de rótulas", "desmontador de amortiguadores", "purgador de frenos",
            "llenador de refrigerante", "kit de palancas de nailon", "kit de clips de coche"
        ],
        "cities": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao", "Zaragoza"],
        "scale_small": ["familiar", "gerenciada por sus dueños", "PYME"]
    },
    "葡萄牙": {
        "lang_code": "pt",
        "country_code": "pt",
        "role_words": ["grossista", "importador", "distribuidor", "fornecedor", "revendedor"],
        "exclude_words": ["oficina", "reparação", "carroçaria", "pintura", "pneus", "industrial", "construção", "jardinagem", "agrícola"],
        "evidence_keywords": [
            "ferramenta de ar condicionado auto", "detector de fugas de radiador", "manifold de refrigeração",
            "testador de compressão", "manómetro de pressão de combustível", "testador de injetores diesel",
            "kit de recuo do travão", "extrator de rótulas", "desmontador de amortecedores", "purga de travões",
            "enchimento de líquido de refrigeração", "kit de alavancas de nylon", "kit de clips automóvel"
        ],
        "cities": ["Lisboa", "Porto", "Braga", "Coimbra", "Faro"],
        "scale_small": ["familiar", "gerida pelo proprietário", "PME"]
    }
}

# ========== 产品目录处理函数 ==========
def parse_product_catalog(uploaded_file):
    """从上传的Excel中提取产品关键词，简单去重"""
    try:
        df = pd.read_excel(uploaded_file)
        # 假设第一列是产品名称或关键词
        if df.shape[1] > 0:
            products = df.iloc[:, 0].dropna().astype(str).tolist()
            # 去重去空
            products = list(set([p.strip() for p in products if p.strip()]))
            return products[:20]  # 最多取20个避免过长
        return []
    except:
        return []

def translate_products(products, target_lang):
    """简单的本地翻译映射（后续可接入翻译API）"""
    # 这里只做预置词典匹配，实际可扩展
    translation_maps = {
        "de": {"气缸压力表": "Zylinderdruckprüfer", "刹车油更换机": "Bremsenentlüftungsgerät",
               "空调加氟表": "Klimaservice-Werkzeug", "水箱测漏仪": "Kühlsystem-Dichtheitsprüfer",
               "柴油喷油嘴测试器": "Dieseleinspritzung-Tester", "球头拉拔器": "Kugelgelenkabzieher",
               "减震器拆装工具": "Fahrwerk-Reparaturwerkzeug", "塑料撬棒套装": "Kunststoff-Nylon-Hebel-Set",
               "汽车卡扣组合": "Auto-Clip-Set"},
        "fr": {"气缸压力表": "testeur de compression", "刹车油更换机": "purgeur de frein",
               "空调加氟表": "manifold frigorifique", "水箱测漏仪": "détecteur de fuite de radiateur"},
        # 其他语言类似...
    }
    # 如果没有预置，直接返回原词（用户应该自己填目标语言词条，或依赖下面的自动翻译逻辑）
    translated = []
    for p in products:
        # 先看映射表
        if target_lang in translation_maps and p in translation_maps[target_lang]:
            translated.append(translation_maps[target_lang][p])
        else:
            # 保留原词，用户可手动修正
            translated.append(p)
    return translated

# ========== 搜索与验证函数 ==========
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

def extract_lead(html, url, config):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()

    # 排除检查
    if contains_any(text, config['exclude_words']):
        return None
    # 角色检查
    if not contains_any(text, config['role_words']):
        return None
    # 产品证据检查（必须出现至少一个证据关键词）
    if not contains_any(text, config['evidence_keywords']):
        return None

    domain = urlparse(url).netloc
    company = soup.title.string.strip() if soup.title else domain

    emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
    emails = [e for e in emails if 'noreply' not in e and 'example' not in e]

    # 社媒
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

    # 规模
    scale_text = text.lower()
    if any(w in scale_text for w in config.get('scale_small', [])):
        scale = "家族/中小型"
    else:
        scale = "推测中小型"

    # 电商
    ecommerce = []
    if 'amazon' in html:
        ecommerce.append("Amazon")
    if 'ebay' in html:
        ecommerce.append("eBay")
    ecommerce_str = ", ".join(ecommerce) if ecommerce else "未发现"

    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    contact = "邮箱: " + (", ".join(emails) if emails else "无") + "; 电话: " + (phones[0] if phones else "官网表单")

    matched = [kw for kw in config['evidence_keywords'] if kw.lower() in text.lower()]

    return {
        '公司名称': company,
        '官网': url,
        '匹配产品': ', '.join(matched[:3]),
        '社媒': socials,
        '规模': scale,
        '电商渠道': ecommerce_str,
        '联系方式': contact,
    }

# ========== 主界面 ==========
with st.sidebar:
    st.header("⚙️ 搜索配置")
    country = st.selectbox("选择目标国家", list(LANGUAGES.keys()))
    config = LANGUAGES[country]

    # 城市选择（自动出现该国城市列表）
    cities = st.multiselect(
        "选择搜索城市（可多选）",
        config['cities'],
        default=config['cities'][:3]  # 默认前3个
    )

    # 上传产品目录
    uploaded_catalog = st.file_uploader("📎 上传产品目录 (Excel)", type=["xlsx"])
    custom_keywords = []
    if uploaded_catalog:
        products = parse_product_catalog(uploaded_catalog)
        if products:
            st.success(f"识别到 {len(products)} 个产品词")
            # 自动翻译（这里是示例，实际可接入翻译库）
            translated = translate_products(products, config['lang_code'])
            # 允许用户手动修正
            st.text_area("自动翻译的关键词（可修改）", value="\n".join(translated), height=150, key="translated_kw")
            if st.button("应用翻译关键词"):
                custom_keywords = [l.strip() for l in st.session_state.translated_kw.split("\n") if l.strip()]
        else:
            st.warning("未能从文件中提取产品词，请检查格式")

    # 如果没有上传产品，则使用预设证据词中的前几个作为搜索词
    if not custom_keywords:
        # 默认用证据关键词生成搜索词
        custom_keywords = config['evidence_keywords'][:8]

    st.markdown("---")
    st.caption("程序将自动组合：[产品词] + [角色词] + [城市] 进行搜索")

if st.button("🚀 开始智能搜索", type="primary"):
    if not cities:
        st.error("请至少选择一个城市")
    else:
        role_samples = random.sample(config['role_words'], min(2, len(config['role_words'])))
        queries = []
        for kw in custom_keywords:
            for role in role_samples:
                for city in cities:
                    queries.append(f"{kw} {role} {city}")

        st.info(f"将执行 {len(queries)} 组搜索...")

        all_leads = []
        seen = set()
        progress = st.progress(0)
        status = st.empty()

        for i, q in enumerate(queries):
            status.text(f"搜索中: {q}")
            progress.progress((i+1)/len(queries))
            try:
                results = search(q, num=5, stop=5, user_agent='Mozilla/5.0',
                                 lang=config['lang_code'], country=config['country_code'])
            except Exception as e:
                st.warning(f"搜索受限: {q} ({e})，跳过")
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
                lead = extract_lead(html, url, config)
                if lead:
                    all_leads.append(lead)
                time.sleep(random.uniform(1, 3))
            time.sleep(2)

        progress.empty()
        status.empty()

        if not all_leads:
            st.warning("未找到完全匹配的公司，请调整关键词或城市重试。")
        else:
            unique = []
            names = set()
            for l in all_leads:
                if l['公司名称'] not in names:
                    names.add(l['公司名称'])
                    unique.append(l)
            final = unique[:5]

            st.success(f"找到 {len(unique)} 家匹配公司，展示前5家")
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

            # 导出
            df = pd.DataFrame(final)
            df['社媒'] = df['社媒'].apply(lambda x: '; '.join([f"{n}: {l}" for n,l in x]) if isinstance(x, list) else x)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载结果 Excel", csv, "leads.csv", "text/csv")
