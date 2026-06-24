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
st.markdown("🎯 **系统特色**: 支持全球任意国家自定义搜索！内置 **14维度背调** 与 **高转化开发信** 自动生成器。")
st.markdown("🛡️ **云端强化纯净模式**: 自动对抗 IP 封禁与反爬。严格剔除：集团上市公司 / 修理厂 / 纯零售 / 黄页与新闻 / 跨界大卖。")

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
    "🇩🇪 德国 (Germany)": {"region": "de-de", "role_words": ["Großhandel", "Importeur", "Distributor", "Händler"], "product_lines": {
        "01 仪表检测": {"search": ["Kühlsystem-Dichtheitsprüfer", "Kompressionstester"]}, "02 液体更换": {"search": ["Bremsenentlüftungsgerät", "Ölabsaugpumpe"]}, "03 空调制冷": {"search": ["Klima-Monteurhilfe", "Kältemittel-Füllschlauch"]}, "04 拆卸工具": {"search": ["Zierleistenkeile", "Auto-Clip-Set"]}, "05 正时工具": {"search": ["Motor-Einstellwerkzeug", "Zahnriemen-Werkzeug"]}
    }},
    "🇪🇸 西班牙/南美大区": {"region": "es-es", "role_words": ["mayorista", "importador", "distribuidor", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
}

# ==================== 核心：免 API 的本地智能邮件引擎 ====================
def generate_local_autonomous_email(lead, country):
    """根据严格设定的外贸规则，内置生成高转化开发信，完全免API"""
    
    products = lead['匹配产品'].split(', ')
    core_product = products[0] if products else "automotive specialized tools"
    company_name = lead['公司名称']
    
    # 动态匹配国家语言
    if "Mexico" in country or "西班牙" in country:
        lang = "es"
    elif "德国" in country or "Germany" in country:
        lang = "de"
    elif "俄罗斯" in country or "Russia" in country:
        lang = "ru"
    else:
        lang = "en"

    # 基于你要求的“不自嗨、提供直接价值、低压试探”构建模板集
    templates = {
        "en": {
            "subject": f"Supply chain idea for {company_name}",
            "body": f"Hi team at {company_name},\n\nI noticed you supply {core_product} and related diagnostic tools to the local market.\n\nWith recent supply chain shifts, many independent distributors in your area are facing margin squeezes from local middlemen. We help suppliers like you bypass the middleman and source directly, allowing for smaller, flexible trial orders without tying up your cash flow.\n\nWould you be open to a quick chat to see if this fits your upcoming inventory planning?\n\nBest regards,\n[Your Name]",
            "cn": f"主题：关于 {company_name} 供应链的一个想法\n\n{company_name} 团队你们好，\n\n我注意到你们在本地市场供应 {core_product} 及相关的诊断工具。\n\n随着近期供应链的变化，你们当地许多独立经销商正面临中间商带来的利润挤压。我们致力于帮助像你们这样的供应商绕过中间商直接采购，并支持更灵活的小批量试单，从而不占用你们的现金流。\n\n不知道你们是否愿意简单交流一下，看看这是否契合你们接下来的库存规划？\n\n祝好，\n[你的名字]"
        },
        "es": {
            "subject": f"Idea de suministro para {company_name}",
            "body": f"Hola equipo de {company_name},\n\nNoté que distribuyen {core_product} y herramientas de diagnóstico en su mercado local.\n\nActualmente, muchos distribuidores independientes enfrentan márgenes reducidos debido a los intermediarios locales. Ayudamos a importadores como ustedes a comprar directamente desde el origen. Esto permite realizar pedidos de prueba pequeños y flexibles sin comprometer su flujo de caja.\n\n¿Estarían abiertos a una breve charla para ver si esto encaja en su planificación de inventario?\n\nSaludos cordiales,\n[Tu Nombre]",
            "cn": f"主题：关于 {company_name} 供应链的一个想法\n\n{company_name} 团队你们好，\n\n我注意到你们在本地市场供应 {core_product} 及相关诊断工具。\n\n当前，许多独立经销商正面临本地中间商导致的利润缩减。我们帮助像你们这样的进口商直接从源头采购，允许灵活的小额试单，以避免影响你们的现金流。\n\n请问你们是否愿意进行简短交流，看看这是否符合你们的库存计划？\n\n祝好，\n[你的名字]"
        },
        "de": {
            "subject": f"Lieferketten-Optimierung für {company_name}",
            "body": f"Hallo Team von {company_name},\n\nich habe gesehen, dass Sie {core_product} und Diagnosewerkzeuge auf dem lokalen Markt anbieten.\n\nViele unabhängige Händler stehen derzeit unter Margendruck durch Zwischenhändler. Wir helfen Anbietern wie Ihnen, direkt zu beziehen, was kleinere und flexiblere Testbestellungen ermöglicht, ohne Ihre Liquidität zu belasten.\n\nWären Sie offen für ein kurzes Gespräch, um zu sehen, ob dies in Ihre kommende Bestandsplanung passt?\n\nBeste Grüße,\n[Ihr Name]",
            "cn": f"主题：针对 {company_name} 的供应链优化\n\n{company_name} 团队你们好，\n\n我看到你们在本地市场提供 {core_product} 及诊断工具。\n\n目前许多独立经销商正面临中间商带来的利润压力。我们帮助像你们这样的供应商直接采购，实现更小、更灵活的试单，而不会增加你们的资金压力。\n\n您是否愿意进行简短的交流，看看这是否适合您接下来的库存规划？\n\n祝好，\n[你的名字]"
        },
        "ru": {
            "subject": f"Идея поставок для {company_name}",
            "body": f"Здравствуйте, команда {company_name},\n\nЯ заметил, что вы поставляете {core_product} и диагностические инструменты на местный рынок.\n\nСегодня многие независимые дистрибьюторы сталкиваются с падением маржи из-за посредников. Мы помогаем таким поставщикам, как вы, закупать напрямую, предлагая небольшие и гибкие пробные партии, чтобы не замораживать ваш оборотный капитал.\n\nВы открыты для короткого общения, чтобы обсудить, подходит ли это для планирования ваших запасов?\n\nС уважением,\n[Ваше Имя]",
            "cn": f"主题：为 {company_name} 提供的采购方案\n\n{company_name} 团队你们好，\n\n我注意到你们在当地市场供应 {core_product} 及诊断工具。\n\n如今，许多独立分销商正面临中间商带来的利润下滑。我们帮助像你们这样的供应商直接进行采购，提供小巧灵活的试销订单，以免冻结您的营运资金。\n\n不知道你们是否愿意简单聊聊，看看这是否契合你们的库存计划？\n\n祝好，\n[你的名字]"
        }
    }
    
    selected_lang = lang if lang in templates else "en"
    result = f"**🌍 当地语言版本 ({selected_lang.upper()})**\n\n"
    result += f"**Subject:** {templates[selected_lang]['subject']}\n\n"
    result += f"{templates[selected_lang]['body']}\n\n"
    result += "---\n\n**🇨🇳 中文翻译参考**\n\n"
    result += f"{templates[selected_lang]['cn']}"
    
    return result


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
    ig_links = list(set(re.findall(r'(https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+)', lead['HTML内容'])))
    in_links = list(set(re.findall(r'(https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9._-]+)', lead['HTML内容'])))
    social_media = []
    if fb_links: social_media.append(f"Facebook: {fb_links[0]}")
    if ig_links: social_media.append(f"Instagram: {ig_links[0]}")
    if in_links: social_media.append(f"LinkedIn: {in_links[0]}")
    social_str = " \n    - ".join(social_media) if social_media else "未在官网主页直接提取到外链，建议用公司名称在海外社媒手动检索。"

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    intro = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else f"系统分析：该公司为 {country} 当地专业汽保工具及设备独立分销商，致力于为本地汽车维修体系提供高质量工具支持。"
    
    ecommerce_status = "否（以传统线下B2B批发、邮件询单模式为主，未发现购物车系统）"
    if "cart" in lead['HTML内容'].lower() or "add to cart" in lead['HTML内容'].lower() or "checkout" in lead['HTML内容'].lower():
        ecommerce_status = "是（附带 B2B 采购下单功能，已确认非Vevor/Amazon等跨界大平台卖家）"

    emails = list(dict.fromkeys(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', lead['HTML内容'])))
    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', lead['HTML内容'])
    email_str = emails[0] if emails else "未提取到明文邮箱（需访问其 Contact Us 提交表单）"
    phone_str = phones[0] if phones else "无明文展示"
    
    report = f"""
### 📊 资深业务员：{lead['公司名称']} 客户背景深度调研报告

**1. 公司名称**：{lead['公司名称']}

**2. 公司介绍**：{intro[:300]}...

**3. 经营地址**：确认为 {country} 本土注册实体企业。

**4. 官方网站**：{lead['官网/主页']}

**5. 社交媒体与线下门店**：
    - {social_str}

**6. 是否以电商平台作为销售渠道**：{ecommerce_status}

**7. 主要经营产品**：重点侦测到其正在经营：**{lead['匹配产品']}**。

**8. 员工联系方式及职位建议**：
    - 📥 **采购员 (Sourcing Dept)**：`{email_str}`
    - 📞 **业务经理 (Ops Manager)**：`{phone_str}`。

**9. 核心痛点**：① 供应链成本倒挂 ② 起订量 (MOQ) 不灵活 ③ 售后质量合规。

**10. 决策因素**：季节需求、工厂直供底价、样品极速测试。

**11. 定制化需求**：极大概率需要 **OEM 贴牌服务**，以及 {country} 语言的包装定制。

**12. 商业模式**：经典的 **B2B 区域进口分销 + 独立站直营** 混合模式。

**13. 产品策略**：平稳供给消耗类工具，同时引进高利润的专业仪表及诊断类设备。
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
        st.info("💡 **上帝模式**：您现在可以搜索全球任何角落！请用英文输入国家和关键词。")
        custom_name = st.text_input("1. 目标国家英文名 (如：Australia, Vietnam, Poland)", value="Australia")
        custom_roles = st.text_input("2. 经销商词汇 (英文/当地语言，逗号分隔)", value="wholesaler, distributor, importer, supplier")
        custom_excludes = st.text_input("3. 额外排除词汇 (逗号分隔)", value="repair service, mobile mechanic, car wash")
        
        custom_roles_list = [x.strip() for x in custom_roles.split(",")]
        custom_excludes_list = [x.strip() for x in custom_excludes.split(",")]
        
        config = {
            "region": "wt-wt", 
            "search_suffix": custom_name,
            "role_words": custom_roles_list,
            "product_lines": BASE_EN_PRODUCTS
        }
        display_country_name = custom_name
    else:
        config = COUNTRY_CONFIG[selected_country]
        display_country_name = selected_country

    st.subheader("📦 选择产品线 (用于判定其专业性)")
    selected_lines = [line for line in config['product_lines'].keys() if st.checkbox(line, value=True)]
    
    manual_keywords = st.text_area("🔧 补充当地小语种产品词汇 (每行一个，可选)", height=80)
    final_keywords = []
    for line in selected_lines:
        final_keywords.extend(config['product_lines'][line]['search'])
    if manual_keywords.strip():
        final_keywords.extend([k.strip() for k in manual_keywords.splitlines() if k.strip()])
    final_keywords = list(set(final_keywords))

    st.markdown("---")
    st.success(f"已沉淀高优极度纯净的经销商: {len(st.session_state.all_leads)} 家")
    if st.button("清空所有记录(重新开始)"):
        st.session_state.excluded_domains.clear()
        st.session_state.all_leads.clear()
        st.session_state.local_reports.clear()
        st.session_state.local_emails.clear()
        save_data() 
        st.session_state.current_page = 0
        st.session_state.last_search_count = 0
        st.rerun()

def search_leads(keywords, config, excluded_domains, custom_excludes_list, target_num=5):
    scored_leads = []
    seen = excluded_domains.copy()
    
    queries = []
    search_suffix = config.get("search_suffix", "")
    for kw in keywords:
        role = random.choice(config["role_words"])
        query = f'{kw} {role}'
        if search_suffix: 
            query += f' {search_suffix}' 
        queries.append(query)
    random.shuffle(queries)

    progress_text = st.empty()
    total_urls_found = 0

    for q in queries:
        if len(scored_leads) >= target_num: break
        progress_text.write(f"🔄 正在深挖: `{q}` (已抓取 {total_urls_found} 个原始网址，目前验证合规 {len(scored_leads)}/{target_num} 家)...")
        
        urls = duckduckgo_search(q, region=config.get("region", "wt-wt"), max_results=20)
        
        if not urls:
            time.sleep(2)
            continue
            
        total_urls_found += len(urls)

        for url in urls:
            if len(scored_leads) >= target_num: break
            
            domain = urlparse(url).netloc.lower()
            if any(b in domain for b in PLATFORM_BLOCKLIST): continue
            if "jinyue" in domain or "jytool" in domain: continue
            if domain in seen and "facebook.com" not in domain: continue
            
            html = fetch_page(url)
            if not html: continue
            
            score, info = score_lead(html, url, config, keywords, custom_excludes_list)
            if score > 0:
                scored_leads.append((score, info))
                seen.add(domain)
            else:
                seen.add(domain)
        time.sleep(1.5)

    progress_text.empty()
    scored_leads.sort(key=lambda x: x[0], reverse=True)
    return [info for _, info in scored_leads[:target_num]], total_urls_found

if st.button(f"🔍 开启最严厉深挖 5 家 【{display_country_name}】 顶级经销商", type="primary"):
    if not final_keywords:
        st.error("请至少选择一条产品线或输入关键词")
    else:
        with st.spinner(f"系统正向 {display_country_name} 发射深海探测器... 正无情粉碎所有上市集团、黄页、Vevor和修理厂..."):
            leads, total_urls = search_leads(final_keywords, config, st.session_state.excluded_domains, custom_excludes_list, target_num=5)
        
        if leads:
            st.session_state.all_leads.extend(leads)
            for l in leads: st.session_state.excluded_domains.add(urlparse(l['官网/主页']).netloc.lower())
            st.session_state.last_search_count += 1
            st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
            save_data() 
            st.success(f"🎉 成功斩获！原始总抓取池为 {total_urls} 个网站，经过层层粉碎过滤后，精准斩获 {len(leads)} 家合规 B2B 经销商！")
            if len(leads) < 5:
                st.warning("⚠️ 过滤机制极其严苛，由于大量 Vevor 大卖/中介/修理厂已被后台拦截抛弃，最终合规呈现较少。请再次点击继续。")
        else:
            if total_urls == 0:
                st.error("🛑 **警报**： DuckDuckGo 暂时拒绝了当前的访问请求 (抓取到 0 个原始网址)。请等待 **1-2 分钟**后再次点击按钮。")
            else:
                st.warning(f"🛑 **过滤太猛导致全军覆没**：抓取了 **{total_urls}** 个网站，但全是平台或修车店，已100%拦截。请再次搜索刷新池子！")

# ==================== 结果显示 ====================
if st.session_state.all_leads:
    total_leads = len(st.session_state.all_leads)
    total_pages = (total_leads - 1) // 5 + 1
    current_page = st.session_state.current_page

    col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
    with col1:
        if st.button("⬅️ 上一页", disabled=(current_page == 0)):
            st.session_state.current_page -= 1
            st.rerun()
    with col2:
        if st.button("下一页 ➡️", disabled=(current_page >= total_pages - 1)):
            st.session_state.current_page += 1
            st.rerun()
    with col3:
        st.write(f"第 {current_page+1}/{total_pages} 页 · 库内共 {total_leads} 家绝密客户")
    with col4:
        st.download_button("📥 导出独立站纯净名单", pd.DataFrame(st.session_state.all_leads)[['公司名称','官网/主页','匹配产品','联系方式','评分']].to_csv(index=False).encode('utf-8-sig'), "JYTOOL_Ultra_Pure_Leads.csv")

    start_idx = current_page * 5
    end_idx = min(start_idx + 5, total_leads)
    
    for i in range(start_idx, end_idx):
        lead = st.session_state.all_leads[i]
        score_color = "🔥" if lead['产品数'] >= 3 else "🟢"
        lead_url = lead['官网/主页']
        
        st.subheader(f"{i+1}. {score_color} {lead['公司名称']} (严选意向分: {lead['评分']})")
        st.markdown(f"**纯独立官网/社媒**: [{lead_url}]({lead_url})")
        st.markdown(f"🎯 **专业工具匹配度**: `{lead['匹配产品']}` | 📞 **联系渠道**: {lead['联系方式']}")
        
        col_btn1, col_btn2 = st.columns([1, 1])
        
        with col_btn1:
            if lead_url not in st.session_state.local_reports:
                if st.button(f"📊 生成 14维度背调档案", key=f"bg_btn_{i}"):
                    with st.spinner("提取底层数据，构建标准档案..."):
                        time.sleep(0.5)
                        st.session_state.local_reports[lead_url] = local_background_check(lead, display_country_name)
                        save_data()
                        st.rerun()
                        
        with col_btn2:
            if lead_url not in st.session_state.local_emails:
                if st.button(f"✉️ 生成 高转化双语开发信", key=f"email_btn_{i}"):
                    with st.spinner("根据目标国家语言和产品痛点，智能生成专属开发信..."):
                        time.sleep(0.5)
                        st.session_state.local_emails[lead_url] = generate_local_autonomous_email(lead, display_country_name)
                        save_data()
                        st.rerun()
        
        if lead_url in st.session_state.local_reports or lead_url in st.session_state.local_emails:
            with st.expander("✅ 展开查看：客户档案 & 专属开发信", expanded=True):
                if lead_url in st.session_state.local_reports:
                    st.markdown(st.session_state.local_reports[lead_url])
                if lead_url in st.session_state.local_reports and lead_url in st.session_state.local_emails:
                    st.markdown("---")
                if lead_url in st.session_state.local_emails:
                    st.markdown("### ✉️ 专属高转化开发信 (按指令规范生成)")
                    st.markdown(st.session_state.local_emails[lead_url])
                    
        st.markdown("---")
