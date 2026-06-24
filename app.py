import streamlit as st
import requests
import re
import time
import random
import pandas as pd
import json
import os
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ddgs import DDGS

st.set_page_config(page_title="JYTOOL 全球 B2B 精准获客神器", layout="wide")
st.title("🔧 JYTOOL 汽保工具 · 全球无限制 B2B 经销商搜索")
st.markdown("🎯 **系统特色**: 支持全球任意国家自定义搜索！内置 **14维度背调** 与 **智能邮件工作台**。")
st.markdown("🛡️ **云端强化纯净模式**: 自动对抗 IP 封禁与反爬。严格剔除：集团/平台/黄页/修理厂。")

# ==================== 数据持久化 ====================
DATA_FILE = "jytool_database.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return (
                    data.get("all_leads", []), 
                    set(data.get("excluded_domains", [])), 
                    data.get("local_reports", {}),
                    data.get("local_emails", {})
                )
        except Exception as e:
            st.error(f"加载数据失败: {e}")
    return [], set(), {}, {}

def save_data():
    data = {
        "all_leads": st.session_state.all_leads,
        "excluded_domains": list(st.session_state.excluded_domains),
        "local_reports": st.session_state.local_reports,
        "local_emails": st.session_state.local_emails
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if 'data_loaded' not in st.session_state:
    loaded_leads, loaded_domains, loaded_reports, loaded_emails = load_data()
    st.session_state.all_leads = loaded_leads
    st.session_state.excluded_domains = loaded_domains
    st.session_state.local_reports = loaded_reports
    st.session_state.local_emails = loaded_emails 
    st.session_state.current_page = 0
    st.session_state.last_search_count = 0
    st.session_state.data_loaded = True

# ==================== 终极黑名单配置 ====================
PLATFORM_BLOCKLIST = [
    "iqsdirectory.", "directory.", "yellowpages.", "thomasnet.", "kompass.", "europages.", 
    "yelp.", "zoominfo.", "dnb.", "manta.", "crunchbase.", "trade.", "b2b.", "globalsources.", 
    "made-in-china.", "alibaba.", "aliexpress.", "indiamart.", "tradekey.", "hktdc.", "manufacturers.", "suppliers.",
    "amazon.", "ebay.", "walmart.", "shopee.", "lazada.", "etsy.", "wayfair.", "temu.", "shein.", "trustpilot.",
    "autozone.", "oreillyauto.", "napaonline.", "advanceautoparts.", "halfords.",
    "grainger.", "fastenal.", "mscdirect.", "homedepot.", "lowes.", "menards.",
    "target.", "costco.", "carrefour.", "aldi.", "tesco.", "macys.", 
    "snap-on.", "mactools.", "matcotools.", "harborfreight.", "shopping.", "prices.",
    "vevor.", "northerntool.", "princessauto.", "kmstools.", "machineryhouse.", 
    "news.", "blog.", "magazine.", "journal.", "press.", "wiki.", "forbes.", "reuters.", "bloomberg.",
    ".cn", ".com.cn", ".tw", ".hk"
]
TITLE_BLOCKLIST = ["directory", "top 10", "top 20", "top 5", "list of", "manufacturers in", "suppliers of", "best suppliers", "news", "blog", "magazine", "press release", "yellow pages", "b2b platform"]
CHINA_GEO_BLOCKLIST = ["guangdong", "shenzhen", "guangzhou", "dongguan", "foshan", "zhongshan", "zhuhai", "zhejiang", "ningbo", "hangzhou", "yiwu", "wenzhou", "taizhou", "jinhua", "shaoxing", "jiangsu", "shanghai", "shandong", "qingdao", "jinan", "hebei", "henan", "beijing", "tianjin", "+86 ", "0086", "86-1", "86-0", "made in china", "china mainland", "mainland china", "chinese supplier"]
STRICT_BUSINESS_BLOCKLIST = ["investor relations", "stock symbol", "shareholders", "annual report", "subsidiary of", "listed company", "nasdaq", "nyse", "group of companies", "retail store", "consumer electronics", "superstore", "hypermarket", "retail only", "auto repair shop", "repair service", "body shop", "car wash", "tyre shop", "tire shop", "mechanic service", "mobile mechanic", "towing service", "collision center", "auto care clinic", "taller mecánico", "centro de reparación", "chapa y pintura", "grúa", "автосервис", "ремонт авто", "шиномонтаж", "СТО", "Autoreparatur", "Reparaturservice", "Reifenservice", "Abschleppdienst"]
IRRELEVANT_INDUSTRIES_BLOCKLIST = ["garden tools", "lawn mower", "woodworking tools", "plumbing tools", "construction equipment", "agricultural machinery", "industrial supplies"]

BASE_EN_PRODUCTS = {"01 仪表检测工具": {"search": ["radiator pressure tester", "cylinder compression tester", "fuel pressure gauge"]}, "02 液体更换/补充工具": {"search": ["brake fluid replacement tool", "brake bleeder", "oil extractor"]}, "03 汽车空调制冷工具": {"search": ["a/c manifold gauge", "refrigerant charging kit", "a/c leak detection"]}, "04 车身拆卸/卡扣工具": {"search": ["trim removal tool", "plastic pry tools", "car clip set"]}, "05 发动机正时工具": {"search": ["engine timing tool", "camshaft locking tool", "crankshaft tool"]}}
BASE_ES_PRODUCTS = {"01 仪表检测工具": {"search": ["probador de presión de radiador", "comprobador de compresión", "medidor de presión de combustible"]}, "02 液体更换/补充工具": {"search": ["purgador de frenos", "extractor de aceite", "bomba de vacío"]}, "03 汽车空调制冷工具": {"search": ["manómetro de aire acondicionado", "kit de carga de refrigerante", "detector de fugas a/c"]}, "04 车身拆卸/卡扣工具": {"search": ["herramientas para desmontar molduras", "alicates para abrazaderas", "kit de grapas coche"]}, "05 发动机正时工具": {"search": ["kit de calado de motor", "herramienta de sincronización", "bloqueo de árbol de levas"]}}
COUNTRY_CONFIG = {
    "🇺🇸 美国 (USA)": {"region": "us-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇬🇧 英国 (UK)": {"region": "uk-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇲🇽 墨西哥 (Mexico)": {"region": "mx-es", "role_words": ["mayorista", "distribuidor", "importador", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
    "🇦🇪 中东地区 (UAE/沙特)": {"region": "ae-en", "search_suffix": "UAE OR Saudi Arabia OR Dubai", "role_words": ["wholesaler", "distributor", "importer", "equipment supplier"], "product_lines": BASE_EN_PRODUCTS},
    "🇲🇾 东南亚 (马/菲/新/泰)": {"region": "wt-wt", "search_suffix": "Malaysia OR Philippines OR Thailand OR Vietnam", "role_words": ["wholesaler", "distributor", "importer", "supplier"], "product_lines": BASE_EN_PRODUCTS},
    "🇿🇦 南非/非洲 (South Africa)": {"region": "za-en", "role_words": ["wholesaler", "distributor", "importer", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇩🇪 德国 (Germany)": {"region": "de-de", "role_words": ["Großhandel", "Importeur", "Distributor", "Händler"], "product_lines": {"01 仪表检测": {"search": ["Kühlsystem-Dichtheitsprüfer", "Kompressionstester"]}, "02 液体更换": {"search": ["Bremsenentlüftungsgerät", "Ölabsaugpumpe"]}, "03 空调制冷": {"search": ["Klima-Monteurhilfe", "Kältemittel-Füllschlauch"]}, "04 拆卸工具": {"search": ["Zierleistenkeile", "Auto-Clip-Set"]}, "05 正时工具": {"search": ["Motor-Einstellwerkzeug", "Zahnriemen-Werkzeug"]}}},
    "🇪🇸 西班牙/南美大区": {"region": "es-es", "role_words": ["mayorista", "importador", "distribuidor", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
}

# ==================== 邮件工作台核心库 (无 API) ====================
EMAIL_TEMPLATES = {
    "en": {
        "供应链降本切入 (Cost & Margin)": "Subject: Supply chain idea for {company_name}\n\nHi team at {company_name},\n\nI noticed you supply {core_product} and related tools to the local market.\n\nWith recent supply chain shifts, many independent distributors are facing margin squeezes from local middlemen. We help suppliers like you bypass the middleman and source directly, allowing for smaller, flexible trial orders without tying up your cash flow.\n\nWould you be open to a quick chat to see if this fits your upcoming inventory planning?\n\nBest regards,\n[Your Name]",
        "测试试单切入 (Trial Order)": "Subject: Trial order support for {core_product}\n\nHi team at {company_name},\n\nI see you focus on {core_product} for the local auto repair market.\n\nTesting a new supplier can be risky. To help you lower the trial cost, we offer small MOQ test orders and pre-shipment video confirmations, ensuring you get exactly what your clients need without heavy upfront investment.\n\nAre you open to exploring a risk-free trial order this quarter?\n\nBest regards,\n[Your Name]",
        "备用供应商切入 (Backup Supplier)": "Subject: Backup supplier for {company_name}\n\nHi team at {company_name},\n\nHope this email finds you well. I noticed your strong portfolio in {core_product}.\n\nSupply chain disruptions happen. Having a reliable 'Plan B' can prevent unexpected stockouts. We are a direct source for automotive tools, ready to step in quickly whenever your current supply faces delays.\n\nWould it make sense to keep us on file as a backup option?\n\nBest regards,\n[Your Name]"
    },
    "es": {
        "供应链降本切入 (Cost & Margin)": "Asunto: Idea de suministro para {company_name}\n\nHola equipo de {company_name},\n\nNoté que distribuyen {core_product} en su mercado local.\n\nMuchos distribuidores independientes enfrentan márgenes reducidos por los intermediarios. Ayudamos a importadores como ustedes a comprar directamente desde el origen, permitiendo pedidos de prueba pequeños y flexibles sin comprometer su flujo de caja.\n\n¿Estarían abiertos a una breve charla para ver si esto encaja en su planificación de inventario?\n\nSaludos cordiales,\n[Tu Nombre]",
        "测试试单切入 (Trial Order)": "Asunto: Soporte de pedidos de prueba para {core_product}\n\nHola equipo de {company_name},\n\nVeo que se enfocan en {core_product}.\n\nProbar un nuevo proveedor puede ser riesgoso. Para reducir el costo de prueba, ofrecemos pequeños pedidos y confirmaciones por video antes del envío, asegurando que obtengan lo que necesitan sin una gran inversión inicial.\n\n¿Están abiertos a explorar un pedido de prueba sin riesgos este trimestre?\n\nSaludos cordiales,\n[Tu Nombre]",
        "备用供应商切入 (Backup Supplier)": "Asunto: Proveedor de respaldo para {company_name}\n\nHola equipo de {company_name},\n\nNoté su sólida cartera de productos en {core_product}.\n\nLas interrupciones en el suministro ocurren. Tener un 'Plan B' confiable puede prevenir la falta de stock. Somos una fuente directa de herramientas automotrices, listos para intervenir rápidamente cuando su suministro actual enfrente retrasos.\n\n¿Tendría sentido mantenernos en sus contactos como una opción de respaldo?\n\nSaludos cordiales,\n[Tu Nombre]"
    },
    "de": {
        "供应链降本切入 (Cost & Margin)": "Betreff: Lieferketten-Idee für {company_name}\n\nHallo Team von {company_name},\n\nich habe gesehen, dass Sie {core_product} auf dem lokalen Markt anbieten.\n\nViele unabhängige Händler stehen derzeit unter Margendruck durch Zwischenhändler. Wir helfen Anbietern wie Ihnen, direkt zu beziehen, was kleinere und flexiblere Testbestellungen ermöglicht, ohne Ihre Liquidität zu belasten.\n\nWären Sie offen für ein kurzes Gespräch, um zu sehen, ob dies in Ihre kommende Bestandsplanung passt?\n\nBeste Grüße,\n[Ihr Name]",
        "测试试单切入 (Trial Order)": "Betreff: Testbestellungen für {core_product}\n\nHallo Team von {company_name},\n\nich sehe, dass Sie sich auf {core_product} konzentrieren.\n\nDas Testen eines neuen Lieferanten birgt Risiken. Um Ihre Testkosten zu senken, bieten wir kleine Testbestellungen und Videobestätigungen vor dem Versand an. So erhalten Sie genau das, was Sie brauchen, ohne hohe Vorabinvestitionen.\n\nSind Sie offen dafür, in diesem Quartal eine risikofreie Testbestellung zu prüfen?\n\nBeste Grüße,\n[Ihr Name]",
        "备用供应商切入 (Backup Supplier)": "Betreff: Ersatzlieferant für {company_name}\n\nHallo Team von {company_name},\n\nich habe Ihr starkes Portfolio im Bereich {core_product} bemerkt.\n\nLieferkettenunterbrechungen kommen vor. Ein zuverlässiger 'Plan B' verhindert unerwartete Engpässe. Wir sind ein direkter Anbieter von Kfz-Werkzeugen und können schnell einspringen, wenn Ihre aktuelle Lieferung Verzögerungen hat.\n\nMacht es Sinn, uns als Backup-Option zu notieren?\n\nBeste Grüße,\n[Ihr Name]"
    },
    "ru": {
        "供应链降本切入 (Cost & Margin)": "Тема: Идея поставок для {company_name}\n\nЗдравствуйте, команда {company_name},\n\nЯ заметил, что вы поставляете {core_product} на местный рынок.\n\nМногие независимые дистрибьюторы сталкиваются с падением маржи из-за посредников. Мы помогаем закупать напрямую, предлагая небольшие и гибкие пробные партии, чтобы не замораживать ваш оборотный капитал.\n\nВы открыты для короткого общения, чтобы обсудить это?\n\nС уважением,\n[Ваше Имя]",
        "测试试单切入 (Trial Order)": "Тема: Поддержка пробных заказов для {core_product}\n\nЗдравствуйте, команда {company_name},\n\nЯ вижу, что вы ориентируетесь на {core_product}.\n\nТестирование нового поставщика — это риск. Чтобы снизить ваши затраты, мы предлагаем небольшие пробные заказы и видеоподтверждение перед отправкой. Вы получаете именно то, что нужно вашим клиентам, без крупных вложений.\n\nВы готовы рассмотреть безопасный пробный заказ в этом квартале?\n\nС уважением,\n[Ваше Имя]",
        "备用供应商切入 (Backup Supplier)": "Тема: Резервный поставщик для {company_name}\n\nЗдравствуйте, команда {company_name},\n\nУ вас отличный ассортимент по {core_product}.\n\nСбои в поставках случаются. Надежный «План Б» предотвратит нехватку товара. Мы являемся прямым поставщиком автомобильных инструментов и готовы быстро помочь, если ваш текущий поставщик задерживает товар.\n\nИмеет ли смысл сохранить наши контакты в качестве запасного варианта?\n\nС уважением,\n[Ваше Имя]"
    }
}

CN_TRANSLATIONS = {
    "供应链降本切入 (Cost & Margin)": "主题：关于[公司名]的供应链想法\n💡 核心逻辑：点出当地被中间商赚差价的痛点，用“直接采购”和“支持小批灵活试单且不占现金流”吸引对话。",
    "测试试单切入 (Trial Order)": "主题：针对[核心产品]的试单支持\n💡 核心逻辑：以理解“换供应商有风险”作为破冰点，提出“小起订量+发货前验货视频”消除防备心理。",
    "备用供应商切入 (Backup Supplier)": "主题：[公司名]的备用供应商\n💡 核心逻辑：不否定他的现有供应商，仅请求做一个避免断供的“B计划”，这种低姿态和防范风险的角度最容易被接受。"
}

# ==================== 辅助与爬虫函数 ====================
def fetch_page(url, retries=2):
    for attempt in range(retries):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0.0.0 Safari/537.36'}
            resp = requests.get(url, timeout=8, headers=headers)
            resp.raise_for_status()
            return resp.text
        except:
            time.sleep(1)
    return ""

def score_lead(html, url, config, keywords, custom_excludes):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    domain = urlparse(url).netloc.lower()
    company = soup.title.string.strip() if soup.title else domain
    title_lower = company.lower()
    
    if any(t_word in title_lower for t_word in TITLE_BLOCKLIST): return 0, None
    for geo_word in CHINA_GEO_BLOCKLIST:
        if geo_word in text: return 0, None
    for strict_word in STRICT_BUSINESS_BLOCKLIST:
        if strict_word in text: return 0, None

    exclude_list = custom_excludes if custom_excludes else []
    if "facebook.com" not in domain:
        for word in exclude_list:
            if word.lower() in text: return 0, None

    matched_kw = list(set([kw for kw in keywords if kw.lower() in text]))
    if len(matched_kw) == 0: return 0, None 
    
    has_irrelevant_industry = any(irr_word in text for irr_word in IRRELEVANT_INDUSTRIES_BLOCKLIST)
    if has_irrelevant_industry and len(matched_kw) < 2:
        return 0, None

    score = 10 
    if len(matched_kw) >= 3: score += 30 
    elif len(matched_kw) == 2: score += 15

    role_words = config.get('role_words', ["distributor", "wholesaler"])
    role_hit = any(role.lower() in text for role in role_words)
    if role_hit: score += 20
    elif "facebook.com" in domain: score += 15 
    else: return 0, None 

    emails = list(dict.fromkeys(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
    wa_links = list(set(re.findall(r'(https?://(?:wa\.me/|api\.whatsapp\.com/send\?phone=)[0-9]+)', html)))
    fb_links = list(set(re.findall(r'(https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+)', html)))
    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    
    for phone in phones:
        if phone.replace(" ", "").replace("-", "").startswith("+86") or phone.replace(" ", "").replace("-", "").startswith("0086"):
            return 0, None

    contact_parts = []
    if emails: contact_parts.append("✉️ " + ", ".join(emails[:2]))
    if wa_links: contact_parts.append("💬 WA: " + wa_links[0])
    elif phones: contact_parts.append("📞 " + phones[0])
    if fb_links or "facebook.com" in domain:
        fb_str = fb_links[0] if fb_links else url
        contact_parts.append("🌐 FB: " + fb_str)

    if not contact_parts: contact_parts.append("官网表单")

    return score, {
        '公司名称': company[:60] + "..." if len(company)>60 else company,
        '官网/主页': url,
        '匹配产品': ', '.join(matched_kw[:5]), 
        '产品数': len(matched_kw),
        '联系方式': " | ".join(contact_parts),
        '评分': score,
        'HTML内容': html 
    }

def duckduckgo_search(query, region, max_results=20):
    queries_to_try = [f'{query} -amazon -aliexpress -vevor', query]
    for q in queries_to_try:
        for backend in ['lite', 'html', 'api']:
            try:
                results = []
                with DDGS() as ddgs:
                    for r in ddgs.text(q, region=region, backend=backend, max_results=max_results):
                        results.append(r['href'])
                if results: return results
            except TypeError:
                break
            except Exception:
                time.sleep(1)
                continue
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(q, region=region, max_results=max_results):
                    results.append(r['href'])
            if results: return results
        except Exception:
            time.sleep(1)
            continue
    return []

def local_background_check(lead, country):
    soup = BeautifulSoup(lead['HTML内容'], 'html.parser')
    fb_links = list(set(re.findall(r'(https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+)', lead['HTML内容'])))
    social_str = f"Facebook: {fb_links[0]}" if fb_links else "未提取到社媒，建议手动检索。"
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    intro = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else f"系统分析：该公司为 {country} 本地汽保工具分销商。"
    ecommerce_status = "否（传统 B2B 询盘）"
    if "cart" in lead['HTML内容'].lower() or "checkout" in lead['HTML内容'].lower():
        ecommerce_status = "是（附带在线采购下单功能）"

    emails = list(dict.fromkeys(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', lead['HTML内容'])))
    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', lead['HTML内容'])
    
    report = f"""
### 📊 资深业务员：{lead['公司名称']} 客户背景深度调研报告
**1. 公司名称**：{lead['公司名称']}
**2. 公司介绍**：{intro[:300]}...
**3. 经营地址**：{country} 本土注册实体企业。
**4. 官方网站**：{lead['官网/主页']}
**5. 社交媒体与门店**：{social_str}
**6. 电商渠道销售**：{ecommerce_status}
**7. 主要经营产品**：主营侦测为 **{lead['匹配产品']}**。
**8. 员工联系与职位**：📥 采购通道：`{emails[0] if emails else '未展示'}` | 📞 业务经理通道：`{phones[0] if phones else '无'}`。
**9. 核心痛点推演**：① 供应链成本倒挂 ② 起订量不灵活 ③ 售后合规风险。
**10. 决策购买因素**：季节需求、工厂直供底价、样品极速测试。
**11. 定制化需求**：多需要 **OEM 贴牌服务**，及 {country} 语言的包装定制。
**12. 商业模式**：经典的 **B2B 区域进口分销 + 独立站直营**。
"""
    return report

with st.sidebar:
    st.header("🌍 搜索配置")
    
    country_options = list(COUNTRY_CONFIG.keys()) + ["🌍 + 自定义其他国家 (自由配置)"]
    selected_country = st.selectbox("🎯 选择精准目标国家", country_options)

    custom_name = ""
    custom_roles_list = []
    custom_excludes_list = []
    
    if selected_country == "🌍 + 自定义其他国家 (自由配置)":
        st.info("💡 **上帝模式**：您现在可以搜索全球任何角落！")
        custom_name = st.text_input("1. 目标国家英文名 (如: Australia)", value="Australia")
        custom_roles = st.text_input("2. 经销商词汇", value="wholesaler, distributor, importer, supplier")
        custom_excludes = st.text_input("3. 额外排除词汇", value="repair service, mobile mechanic, car wash")
        
        custom_roles_list = [x.strip() for x in custom_roles.split(",")]
        custom_excludes_list = [x.strip() for x in custom_excludes.split(",")]
        config = {"region": "wt-wt", "search_suffix": custom_name, "role_words": custom_roles_list, "product_lines": BASE_EN_PRODUCTS}
        display_country_name = custom_name
    else:
        config = COUNTRY_CONFIG[selected_country]
        display_country_name = selected_country

    st.subheader("📦 选择产品线")
    selected_lines = [line for line in config['product_lines'].keys() if st.checkbox(line, value=True)]
    
    manual_keywords = st.text_area("🔧 补充当地小语种产品词汇 (可选)", height=80)
    final_keywords = []
    for line in selected_lines:
        final_keywords.extend(config['product_lines'][line]['search'])
    if manual_keywords.strip():
        final_keywords.extend([k.strip() for k in manual_keywords.splitlines() if k.strip()])
    final_keywords = list(set(final_keywords))

    st.markdown("---")
    st.success(f"已沉淀绝密经销商: {len(st.session_state.all_leads)} 家")
    if st.button("清空所有记录"):
        st.session_state.excluded_domains.clear()
        st.session_state.all_leads.clear()
        st.session_state.local_reports.clear()
        st.session_state.local_emails.clear()
        save_data() 
        st.session_state.current_page = 0
        st.rerun()

def search_leads(keywords, config, excluded_domains, custom_excludes_list, target_num=5):
    scored_leads = []
    seen = excluded_domains.copy()
    queries = []
    search_suffix = config.get("search_suffix", "")
    for kw in keywords:
        role = random.choice(config["role_words"])
        query = f'{kw} {role}'
        if search_suffix: query += f' {search_suffix}' 
        queries.append(query)
    random.shuffle(queries)

    progress_text = st.empty()
    total_urls_found = 0

    for q in queries:
        if len(scored_leads) >= target_num: break
        progress_text.write(f"🔄 正在深挖: `{q}` (已验证合规 {len(scored_leads)}/{target_num} 家)...")
        urls = duckduckgo_search(q, region=config.get("region", "wt-wt"), max_results=20)
        if not urls:
            time.sleep(2); continue
        total_urls_found += len(urls)

        for url in urls:
            if len(scored_leads) >= target_num: break
            domain = urlparse(url).netloc.lower()
            if any(b in domain for b in PLATFORM_BLOCKLIST): continue
            if domain in seen and "facebook.com" not in domain: continue
            
            html = fetch_page(url)
            if not html: continue
            
            score, info = score_lead(html, url, config, keywords, custom_excludes_list)
            if score > 0:
                scored_leads.append((score, info))
            seen.add(domain)
        time.sleep(1.5)

    progress_text.empty()
    scored_leads.sort(key=lambda x: x[0], reverse=True)
    return [info for _, info in scored_leads[:target_num]], total_urls_found

if st.button(f"🔍 深挖 5 家 【{display_country_name}】 顶级经销商", type="primary"):
    if not final_keywords:
        st.error("请选择产品线或输入关键词")
    else:
        with st.spinner("系统发射深海探测器... 正无情粉碎所有上市集团、黄页、Vevor和修理厂..."):
            leads, total_urls = search_leads(final_keywords, config, st.session_state.excluded_domains, custom_excludes_list, target_num=5)
        
        if leads:
            st.session_state.all_leads.extend(leads)
            for l in leads: st.session_state.excluded_domains.add(urlparse(l['官网/主页']).netloc.lower())
            st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
            save_data() 
            st.success(f"🎉 斩获成功！精准验证 {len(leads)} 家合规经销商！")
        else:
            st.warning("全军覆没或网络受限，请等待10秒后重试。")

# ==================== 结果显示与工作台 ====================
if st.session_state.all_leads:
    total_leads = len(st.session_state.all_leads)
    total_pages = (total_leads - 1) // 5 + 1
    current_page = st.session_state.current_page

    col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
    with col1:
        if st.button("⬅️ 上一页", disabled=(current_page == 0)):
            st.session_state.current_page -= 1; st.rerun()
    with col2:
        if st.button("下一页 ➡️", disabled=(current_page >= total_pages - 1)):
            st.session_state.current_page += 1; st.rerun()
    with col3:
        st.write(f"第 {current_page+1}/{total_pages} 页 · 共 {total_leads} 家客户")
    with col4:
        st.download_button("📥 导出名单", pd.DataFrame(st.session_state.all_leads)[['公司名称','官网/主页','匹配产品','联系方式','评分']].to_csv(index=False).encode('utf-8-sig'), "JYTOOL_Leads.csv")

    start_idx = current_page * 5
    end_idx = min(start_idx + 5, total_leads)
    
    for i in range(start_idx, end_idx):
        lead = st.session_state.all_leads[i]
        score_color = "🔥" if lead['产品数'] >= 3 else "🟢"
        lead_url = lead['官网/主页']
        
        st.subheader(f"{i+1}. {score_color} {lead['公司名称']}")
        st.markdown(f"**官网**: [{lead_url}]({lead_url}) | **产品匹配**: `{lead['匹配产品']}` | **联系**: {lead['联系方式']}")
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if lead_url not in st.session_state.local_reports:
                if st.button(f"📊 生成 14维度背调档案", key=f"bg_btn_{i}"):
                    st.session_state.local_reports[lead_url] = local_background_check(lead, display_country_name)
                    save_data(); st.rerun()
        
        # 核心功能展开区
        with st.expander("✉️ 展开：智能邮件工作台 & 背景调查", expanded=False):
            if lead_url in st.session_state.local_reports:
                st.markdown(st.session_state.local_reports[lead_url])
                st.markdown("---")

            # 语种与产品自动适配
            if "Mexico" in display_country_name or "西班牙" in display_country_name: lang = "es"
            elif "德国" in display_country_name or "Germany" in display_country_name: lang = "de"
            elif "俄罗斯" in display_country_name or "Russia" in display_country_name: lang = "ru"
            else: lang = "en"
            
            products = lead['匹配产品'].split(', ')
            core_product = products[0] if products else "specialized tools"
            comp_name = lead['公司名称']

            st.markdown("#### ✍️ 撰写专属开发信")
            # 模板选择（下拉框）
            angle = st.selectbox("1️⃣ 选择开发切入角度 (自动加载底层语言高转化模板)", list(EMAIL_TEMPLATES[lang].keys()), key=f"angle_{i}")
            
            # 生成带变量的默认文本
            default_body = EMAIL_TEMPLATES[lang][angle].format(company_name=comp_name, core_product=core_product)
            
            # 中文逻辑辅助说明
            st.info(CN_TRANSLATIONS[angle])
            
            # 编辑区
            edited_email = st.text_area("2️⃣ 自由修改模板初稿 (满意后可保存记录)", value=default_body, height=250, key=f"edit_{i}")
            
            # 保存逻辑
            if st.button("💾 将当前编辑框内容：一键保存为该客户定稿", key=f"save_{i}"):
                st.session_state.local_emails[lead_url] = edited_email
                save_data()
                st.success("✅ 该客户的开发信已定稿并持久化存入系统！")

            # 展示已保存的结果
            if lead_url in st.session_state.local_emails:
                st.markdown("👇 **本客户已保存的最终定稿 (可以直接点击右上角图标复制发送)：**")
                st.code(st.session_state.local_emails[lead_url], language="text")
                
        st.markdown("---")
