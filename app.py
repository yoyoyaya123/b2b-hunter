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
import io

st.set_page_config(page_title="B2B全球智能获客地图", layout="wide")
st.title("🌍 汽车维修专用工具 · 全球B2B精准获客系统")

# ==================== 多语言包 ====================
BUILTIN_LANGUAGES = {
    "德国": {
        "lang_code": "de", "country_code": "de",
        "role_words": ["Großhandel", "Großhändler", "Importeur", "Import", "Distributor", "Händler", "Lieferant", "Fachhandel", "Wiederverkäufer"],
        "exclude_words": ["Werkstatt", "Reparatur", "Service-Center", "Autohaus", "Reifenservice", "Karosseriebau", "Lackiererei", "Tuning", "Industrie", "Baumaschinen", "Gartengeräte", "Landwirtschaft"],
        "evidence_keywords": ["Bremskolbenrückstellsatz", "Zylinderdruckprüfer", "Klimaservice-Werkzeug", "Bremsenentlüftungsgerät", "Kraftstoffdruckmessgerät", "Kühlsystem-Dichtheitsprüfer", "Dieseleinspritzung-Tester", "Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set", "Kugelgelenkabzieher", "Kupplungszentrierwerkzeug"],
        "cities": ["Berlin", "Hamburg", "München", "Frankfurt", "Stuttgart", "Köln", "Düsseldorf"]
    },
    "法国": {
        "lang_code": "fr", "country_code": "fr",
        "role_words": ["grossiste", "importateur", "distributeur", "fournisseur", "revendeur", "commerce de gros"],
        "exclude_words": ["garage", "atelier de réparation", "carrosserie", "peinture", "pneumatique", "industriel", "bâtiment", "jardinage", "agricole"],
        "evidence_keywords": ["outil de climatisation auto", "détecteur de fuite de radiateur", "manifold frigorifique", "testeur de compression", "manomètre de pression d'essence", "testeur d'injecteur diesel", "kit de repose-culasse", "extracteur de rotule", "démonte-amortisseur", "purgeur de frein", "remplisseur de liquide de refroidissement", "kit de leviers en nylon", "kit de clips auto"],
        "cities": ["Paris", "Lyon", "Marseille", "Lille", "Bordeaux", "Toulouse", "Nantes"]
    },
    "西班牙": {
        "lang_code": "es", "country_code": "es",
        "role_words": ["mayorista", "importador", "distribuidor", "proveedor", "comercio al por mayor"],
        "exclude_words": ["taller", "reparación", "carrocería", "pintura", "neumáticos", "industrial", "construcción", "jardinería", "agrícola"],
        "evidence_keywords": ["herramienta de climatización", "probador de fugas de radiador", "manómetro de refrigerante", "comprobador de compresión", "manómetro de presión de combustible", "probador de inyectores diésel", "juego de retroceso de freno", "extractor de rótulas", "desmontador de amortiguadores", "purgador de frenos", "llenador de refrigerante", "kit de palancas de nailon", "kit de clips de coche"],
        "cities": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao", "Zaragoza"]
    },
    "葡萄牙": {
        "lang_code": "pt", "country_code": "pt",
        "role_words": ["grossista", "importador", "distribuidor", "fornecedor", "revendedor"],
        "exclude_words": ["oficina", "reparação", "carroçaria", "pintura", "pneus", "industrial", "construção", "jardinagem", "agrícola"],
        "evidence_keywords": ["ferramenta de ar condicionado auto", "detector de fugas de radiador", "manifold de refrigeração", "testador de compressão", "manómetro de pressão de combustível", "testador de injetores diesel", "kit de recuo do travão", "extrator de rótulas", "desmontador de amortecedores", "purga de travões", "enchimento de líquido de refrigeração", "kit de alavancas de nylon", "kit de clips automóvel"],
        "cities": ["Lisboa", "Porto", "Braga", "Coimbra", "Faro"]
    },
    "意大利": {
        "lang_code": "it", "country_code": "it",
        "role_words": ["grossista", "importatore", "distributore", "fornitore", "rivenditore"],
        "exclude_words": ["officina", "riparazione", "carrozzeria", "verniciatura", "pneumatici", "industriale", "edilizia", "giardinaggio", "agricoltura"],
        "evidence_keywords": ["attrezzo per aria condizionata", "tester perdite radiatore", "manifold refrigerante", "tester di compressione", "manometro pressione carburante", "tester iniettori diesel", "kit rientro pistoncini freno", "estrattore giunti sferici", "smontatore ammortizzatori", "spurgo freni", "riempimento liquido raffreddamento", "set leve in nylon", "set clip auto"],
        "cities": ["Milano", "Roma", "Napoli", "Torino", "Bologna", "Firenze"]
    },
    "荷兰": {
        "lang_code": "nl", "country_code": "nl",
        "role_words": ["groothandel", "importeur", "distributeur", "leverancier"],
        "exclude_words": ["garage", "reparatie", "carrosserie", "spuiterij", "banden", "industrieel", "bouw", "tuin", "landbouw"],
        "evidence_keywords": ["aircogereedschap", "radiateurlektester", "koelsysteemtester", "compressietester", "brandstofdrukmeter", "dieselverstuivertester", "remzuigerterugstelset", "kogelgewrichttrekker", "schokdempergereedschap", "remontluchter", "koelvloeistofvulset", "kunststofhefboomsets", "autoclipsets"],
        "cities": ["Amsterdam", "Rotterdam", "Den Haag", "Utrecht", "Eindhoven"]
    },
    "波兰": {
        "lang_code": "pl", "country_code": "pl",
        "role_words": ["hurtownia", "importer", "dystrybutor", "dostawca"],
        "exclude_words": ["warsztat", "naprawa", "blacharstwo", "lakiernictwo", "opony", "przemysłowy", "budowlany", "ogrodowy", "rolniczy"],
        "evidence_keywords": ["narzędzia do klimatyzacji", "tester szczelności chłodnicy", "manifold chłodniczy", "tester ciśnienia sprężania", "manometr paliwa", "tester wtrysków diesla", "zestaw do cofania tłoczków hamulcowych", "ściągacz przegubów", "narzędzia do amortyzatorów", "odpowietrznik hamulców", "zestaw do napełniania płynu chłodniczego", "zestaw dźwigni z tworzywa", "zestaw klipsów samochodowych"],
        "cities": ["Warszawa", "Kraków", "Łódź", "Wrocław", "Poznań", "Gdańsk"]
    },
    "土耳其": {
        "lang_code": "tr", "country_code": "tr",
        "role_words": ["toptancı", "ithalatçı", "distribütör", "tedarikçi"],
        "exclude_words": ["tamirhane", "kaporta", "boya", "lastik", "endüstriyel", "inşaat", "bahçe", "tarım"],
        "evidence_keywords": ["klima servis aleti", "radyatör kaçak test cihazı", "soğutma sistemi test cihazı", "kompresyon test cihazı", "yakıt basınç ölçer", "dizel enjektör test cihazı", "fren pistonu geri döndürme seti", "rotil çekici", "amortisör sökme takımı", "fren hava alma cihazı", "soğutma sıvısı dolum seti", "naylon levye seti", "oto klips seti"],
        "cities": ["İstanbul", "Ankara", "İzmir", "Bursa", "Konya"]
    },
    "英国": {
        "lang_code": "en", "country_code": "uk",
        "role_words": ["wholesaler", "importer", "distributor", "supplier"],
        "exclude_words": ["garage", "repair", "body shop", "paint", "tyre", "industrial", "construction", "garden", "agricultural"],
        "evidence_keywords": ["air conditioning service tool", "radiator leak tester", "cooling system tester", "compression tester", "fuel pressure gauge", "diesel injector tester", "brake piston wind-back kit", "ball joint puller", "shock absorber tool", "brake bleeder", "coolant fill set", "nylon pry bar set", "car clip set"],
        "cities": ["London", "Birmingham", "Manchester", "Glasgow", "Liverpool", "Bristol"]
    },
    "美国": {
        "lang_code": "en", "country_code": "us",
        "role_words": ["wholesaler", "importer", "distributor", "supplier"],
        "exclude_words": ["garage", "repair", "body shop", "paint", "tire", "industrial", "construction", "garden", "agricultural"],
        "evidence_keywords": ["air conditioning service tool", "radiator leak tester", "cooling system tester", "compression tester", "fuel pressure gauge", "diesel injector tester", "brake piston wind-back kit", "ball joint puller", "shock absorber tool", "brake bleeder", "coolant fill set", "nylon pry bar set", "car clip set"],
        "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Miami", "Dallas"]
    }
}

ALL_COUNTRIES = list(BUILTIN_LANGUAGES.keys()) + ["🌐 自定义"]

# ==================== PDF 解析（支持中英文扫描件OCR） ====================
def extract_text_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        if text.strip():
            return text.strip()
    except:
        pass

    # 文本为空，启动OCR（语言含中文简体和英文）
    try:
        pdf_file.seek(0)
        images = convert_from_bytes(pdf_file.read(), dpi=300)
        ocr_text = ""
        for img in images:
            # ★ 这里已加入 chi_sim（简体中文）★
            ocr_text += pytesseract.image_to_string(img, lang='eng+chi_sim+deu+fra+spa+por') + "\n"
        if ocr_text.strip():
            return ocr_text.strip()
    except Exception as e:
        st.error(f"OCR解析失败: {e}")
    return None

def get_candidate_keywords(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    candidates = [line for line in lines if 5 < len(line) < 200 and not line.startswith("http")]
    return candidates[:50]

# ==================== 其他辅助函数 ====================
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

    if contains_any(text, config['exclude_words']):
        return None
    if not contains_any(text, config['role_words']):
        return None
    if not contains_any(text, config['evidence_keywords']):
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
    if any(w in text.lower() for w in config.get('scale_small', [])):
        scale = "家族/中小型"

    ecommerce = []
    if 'amazon' in html:
        ecommerce.append("Amazon")
    if 'ebay' in html:
        ecommerce.append("eBay")
    ecommerce_str = ", ".join(ecommerce) if ecommerce else "未发现"

    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    contact = "邮箱: " + (", ".join(emails) if emails else "无") + "; 电话: " + (phones[0] if phones else "官网表单")

    matched = [kw for kw in config['evidence_keywords'] if kw.lower() in text.lower()]
    address = extract_address_from_html(html)

    return {
        '公司名称': company,
        '官网': url,
        '匹配产品': ', '.join(matched[:3]),
        '社媒': socials,
        '规模': scale,
        '电商渠道': ecommerce_str,
        '联系方式': contact,
        '地址': address
    }

def extract_address_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    addr = soup.find('address')
    if addr:
        return addr.get_text(separator=" ", strip=True)
    match = re.search(r'\b\d{4,5}\s[A-Za-zäöüßÄÖÜ]{2,30}\b', soup.get_text())
    if match:
        return match.group(0)
    return None

# ==================== 主界面 ====================
with st.sidebar:
    st.header("⚙️ 搜索配置")
    country = st.selectbox("选择目标国家", ALL_COUNTRIES)

    if country == "🌐 自定义":
        lang_code = st.text_input("语言代码", "de")
        country_code = st.text_input("国家代码", "de")
        role_words_str = st.text_area("经销商角色词（每行一个）", "Großhandel\nImporteur\nDistributor")
        exclude_words_str = st.text_area("强制排除词（每行一个）", "Werkstatt\nReparatur\nIndustrie")
        evidence_str = st.text_area("产品证据关键词（每行一个）", "Bremskolbenrückstellsatz\nZylinderdruckprüfer")
        cities_str = st.text_area("搜索城市（每行一个）", "Berlin\nHamburg\nMünchen")
        config = {
            "lang_code": lang_code,
            "country_code": country_code,
            "role_words": [w.strip() for w in role_words_str.splitlines() if w.strip()],
            "exclude_words": [w.strip() for w in exclude_words_str.splitlines() if w.strip()],
            "evidence_keywords": [w.strip() for w in evidence_str.splitlines() if w.strip()],
            "cities": [c.strip() for c in cities_str.splitlines() if c.strip()],
            "scale_small": []
        }
    else:
        config = BUILTIN_LANGUAGES[country]
        role_words_str = st.text_area("经销商角色词（可编辑）", "\n".join(config['role_words']))
        exclude_words_str = st.text_area("强制排除词（可编辑）", "\n".join(config['exclude_words']))
        evidence_str = st.text_area("产品证据关键词（可编辑）", "\n".join(config['evidence_keywords']))
        config['role_words'] = [w.strip() for w in role_words_str.splitlines() if w.strip()]
        config['exclude_words'] = [w.strip() for w in exclude_words_str.splitlines() if w.strip()]
        config['evidence_keywords'] = [w.strip() for w in evidence_str.splitlines() if w.strip()]

    cities = st.multiselect("选择搜索城市（可多选）", config['cities'], default=config['cities'][:3])

    pdf_file = st.file_uploader("📄 上传产品目录（PDF，支持扫描件）", type=["pdf"])
    product_keywords = config['evidence_keywords'][:5]
    if pdf_file:
        pdf_text = extract_text_from_pdf(pdf_file)
        if pdf_text:
            st.success("PDF内容已解析")
            candidates = get_candidate_keywords(pdf_text)
            default_kw = "\n".join(candidates[:15]) if candidates else "\n".join(config['evidence_keywords'][:10])
            product_kw_str = st.text_area("自动提取的产品关键词（可修改）", value=default_kw, height=200)
            product_keywords = [l.strip() for l in product_kw_str.splitlines() if l.strip()]
        else:
            st.error("PDF解析失败，请检查文件是否为文本或清晰的扫描件。")
    else:
        st.info("未上传产品目录，将使用右侧默认关键词。")

    google_api_key = st.text_input("Google Maps API密钥（可选，用于地图显示）", type="password")

if st.button("🚀 开始全球搜索", type="primary"):
    if not cities or not product_keywords:
        st.error("请至少选择一个城市并确保有关键词。")
    else:
        role_samples = random.sample(config['role_words'], min(2, len(config['role_words'])))
        queries = []
        for kw in product_keywords:
            for role in role_samples:
                for city in cities:
                    queries.append(f"{kw} {role} {city}")

        st.info(f"执行 {len(queries)} 组搜索...")
        all_leads = []
        seen = set()
        progress = st.progress(0)
        status = st.empty()

        for i, q in enumerate(queries):
            status.text(f"搜索: {q}")
            progress.progress((i+1)/len(queries))
            try:
                results = search(q, num=5, stop=5, user_agent='Mozilla/5.0',
                                 lang=config.get('lang_code','en'), country=config.get('country_code',''))
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
                lead = extract_lead(html, url, config)
                if lead:
                    all_leads.append(lead)
                time.sleep(random.uniform(1,3))
            time.sleep(2)

        progress.empty()
        status.empty()

        if not all_leads:
            st.warning("未找到匹配公司。")
        else:
            unique = []
            names = set()
            for l in all_leads:
                if l['公司名称'] not in names:
                    names.add(l['公司名称'])
                    unique.append(l)
            final = unique[:8]

            st.success(f"找到 {len(unique)} 家，展示前 {len(final)} 家。")
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
                    if lead['地址']:
                        st.markdown(f"📍 地址: {lead['地址']}")
                    st.markdown("---")

            df = pd.DataFrame(final)
            df['社媒'] = df['社媒'].apply(lambda x: '; '.join([f"{n}: {l}" for n,l in x]) if isinstance(x, list) else x)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载结果 CSV", csv, "leads.csv", "text/csv")
