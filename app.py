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
st.markdown("🎯 **系统特色**: 支持全球任意国家自定义搜索！内置 **14维度标准客户背调档案** 自动生成器。")
st.markdown("🛡️ **极致纯净模式**: 已开启最高级别过滤（严格剔除：集团上市公司 / 修理厂 / 纯零售 / 黄页与新闻 / Vevor类跨界大卖 / 泛工业与通用工具站）")

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
                    data.get("local_reports", {})
                )
        except Exception as e:
            st.error(f"加载数据失败: {e}")
    return [], set(), {}

def save_data():
    data = {
        "all_leads": st.session_state.all_leads,
        "excluded_domains": list(st.session_state.excluded_domains),
        "local_reports": st.session_state.local_reports
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if 'data_loaded' not in st.session_state:
    loaded_leads, loaded_domains, loaded_reports = load_data()
    st.session_state.all_leads = loaded_leads
    st.session_state.excluded_domains = loaded_domains
    st.session_state.local_reports = loaded_reports
    st.session_state.current_page = 0
    st.session_state.last_search_count = 0
    st.session_state.data_loaded = True


# ==================== 终极黑名单配置 (核心修改区) ====================

# 1. 域名级屏蔽：平台、黄页、新闻、大型零售跨界大卖(如vevor)
PLATFORM_BLOCKLIST = [
    # 传统黄页与 B2B
    "iqsdirectory.", "directory.", "yellowpages.", "thomasnet.", "kompass.", "europages.", 
    "yelp.", "zoominfo.", "dnb.", "manta.", "crunchbase.", "trade.", "b2b.", "globalsources.", 
    "made-in-china.", "alibaba.", "aliexpress.", "indiamart.", "tradekey.", "hktdc.", "manufacturers.", "suppliers.",
    # 全球连锁巨头、B2C 比价、跨界大卖
    "amazon.", "ebay.", "walmart.", "shopee.", "lazada.", "etsy.", "wayfair.", "temu.", "shein.", "trustpilot.",
    "autozone.", "oreillyauto.", "napaonline.", "advanceautoparts.", "halfords.",
    "grainger.", "fastenal.", "mscdirect.", "homedepot.", "lowes.", "menards.",
    "target.", "costco.", "carrefour.", "aldi.", "tesco.", "macys.", 
    "snap-on.", "mactools.", "matcotools.", "harborfreight.", "shopping.", "prices.",
    "vevor.", "northerntool.", "princessauto.", "kmstools.", "machineryhouse.", # 拦截 Vevor 及类似泛五金巨头
    # 新闻、杂志、聚合博客站
    "news.", "blog.", "magazine.", "journal.", "press.", "wiki.", "forbes.", "reuters.", "bloomberg.",
    ".cn", ".com.cn", ".tw", ".hk"
]

# 2. 标题级屏蔽：排除黄页集合、排行榜、新闻博客
TITLE_BLOCKLIST = [
    "directory", "top 10", "top 20", "top 5", "list of", "manufacturers in", "suppliers of", "best suppliers",
    "news", "blog", "magazine", "press release", "yellow pages", "b2b platform"
]

CHINA_GEO_BLOCKLIST = [
    "guangdong", "shenzhen", "guangzhou", "dongguan", "foshan", "zhongshan", "zhuhai",
    "zhejiang", "ningbo", "hangzhou", "yiwu", "wenzhou", "taizhou", "jinhua", "shaoxing",
    "jiangsu", "shanghai", "shandong", "qingdao", "jinan", "hebei", "henan",
    "beijing", "tianjin", "+86 ", "0086", "86-1", "86-0", 
    "made in china", "china mainland", "mainland china", "chinese supplier"
]

# 3. 严格商业模式排查：一票否决（包含大型上市集团、纯零售店、各类汽修个体户/服务站）
STRICT_BUSINESS_BLOCKLIST = [
    # 大型上市/集团企业专属词
    "investor relations", "stock symbol", "shareholders", "annual report", "subsidiary of",
    "listed company", "nasdaq", "nyse", "group of companies",
    # 纯零售/商超/消费电子
    "retail store", "consumer electronics", "superstore", "hypermarket", "retail only",
    # 多语言 - 各类修理厂 / 轮胎店 / 钣喷店 / 上门维修服务
    "auto repair shop", "repair service", "body shop", "car wash", "tyre shop", "tire shop",
    "mechanic service", "mobile mechanic", "towing service", "collision center", "auto care clinic",
    "taller mecánico", "centro de reparación", "chapa y pintura", "grúa", # 西班牙语区
    "автосервис", "ремонт авто", "шиномонтаж", "СТО", # 俄语区
    "Autoreparatur", "Reparaturservice", "Reifenservice", "Abschleppdienst" # 德语区
]

# 4. 泛工业/建筑/花园类排查 (若未包含汽车专用工具将直接被丢弃)
IRRELEVANT_INDUSTRIES_BLOCKLIST = [
    "garden tools", "lawn mower", "woodworking tools", "plumbing tools", "construction equipment", 
    "agricultural machinery", "industrial supplies"
]

# ==================== 底层产品基础词库 ====================
BASE_EN_PRODUCTS = {
    "01 仪表检测工具": {"search": ["radiator pressure tester", "cylinder compression tester", "fuel pressure gauge"]},
    "02 液体更换/补充工具": {"search": ["brake fluid replacement tool", "brake bleeder", "oil extractor"]},
    "03 汽车空调制冷工具": {"search": ["a/c manifold gauge", "refrigerant charging kit", "a/c leak detection"]},
    "04 车身拆卸/卡扣工具": {"search": ["trim removal tool", "plastic pry tools", "car clip set"]},
    "05 发动机正时工具": {"search": ["engine timing tool", "camshaft locking tool", "crankshaft tool"]}
}

BASE_ES_PRODUCTS = {
    "01 仪表检测工具": {"search": ["probador de presión de radiador", "comprobador de compresión", "medidor de presión de combustible"]},
    "02 液体更换/补充工具": {"search": ["purgador de frenos", "extractor de aceite", "bomba de vacío"]},
    "03 汽车空调制冷工具": {"search": ["manómetro de aire acondicionado", "kit de carga de refrigerante", "detector de fugas a/c"]},
    "04 车身拆卸/卡扣工具": {"search": ["herramientas para desmontar molduras", "alicates para abrazaderas", "kit de grapas coche"]},
    "05 发动机正时工具": {"search": ["kit de calado de motor", "herramienta de sincronización", "bloqueo de árbol de levas"]}
}

BASE_RU_PRODUCTS = { 
    "01 仪表检测工具": {"search": ["Тестер давления радиатора", "Компрессометр", "Манометр давления топлива"]},
    "02 液体更换/补充工具": {"search": ["Устройство для замены тормозной жидкости", "Вакуумный насос для масла"]},
    "03 汽车空调制冷工具": {"search": ["Манометрическая станция", "Набор для заправки кондиционера", "Детектор утечек фреона"]},
    "04 车身拆卸/卡扣工具": {"search": ["Набор для снятия обшивки", "Клипсы автомобильные"]},
    "05 发动机正时工具": {"search": ["Набор для установки фаз ГРМ", "Фиксатор распредвала"]}
}

# ==================== 独立国家精细化配置 ====================
COUNTRY_CONFIG = {
    "🇺🇸 美国 (USA)": {"region": "us-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇬🇧 英国 (UK)": {"region": "uk-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇲🇽 墨西哥 (Mexico)": {"region": "mx-es", "role_words": ["mayorista", "distribuidor", "importador", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
    "🇷🇺 俄罗斯 (Russia)": {"region": "ru-ru", "role_words": ["оптовик", "дистрибьютор", "импортер", "поставщик"], "product_lines": BASE_RU_PRODUCTS},
    "🇦🇪 中东地区 (UAE/沙特)": {"region": "ae-en", "search_suffix": "UAE OR Saudi Arabia OR Dubai", "role_words": ["wholesaler", "distributor", "importer", "equipment supplier"], "product_lines": BASE_EN_PRODUCTS},
    "🇲🇾 东南亚 (马/菲/新/泰)": {"region": "wt-wt", "search_suffix": "Malaysia OR Philippines OR Thailand OR Vietnam", "role_words": ["wholesaler", "distributor", "importer", "supplier"], "product_lines": BASE_EN_PRODUCTS},
    "🇿🇦 南非/非洲 (South Africa)": {"region": "za-en", "role_words": ["wholesaler", "distributor", "importer", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇱🇰 斯里兰卡 (Sri Lanka)": {"region": "lk-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇩🇪 德国 (Germany)": {"region": "de-de", "role_words": ["Großhandel", "Importeur", "Distributor", "Händler"], "product_lines": {
        "01 仪表检测": {"search": ["Kühlsystem-Dichtheitsprüfer", "Kompressionstester"]}, "02 液体更换": {"search": ["Bremsenentlüftungsgerät", "Ölabsaugpumpe"]}, "03 空调制冷": {"search": ["Klima-Monteurhilfe", "Kältemittel-Füllschlauch"]}, "04 拆卸工具": {"search": ["Zierleistenkeile", "Auto-Clip-Set"]}, "05 正时工具": {"search": ["Motor-Einstellwerkzeug", "Zahnriemen-Werkzeug"]}
    }},
    "🇪🇸 西班牙/南美大区": {"region": "es-es", "role_words": ["mayorista", "importador", "distribuidor", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
}

# ==================== 辅助函数 ====================
def fetch_page(url, retries=2):
    for attempt in range(retries):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0.0.0 Safari/537.36'}
            resp = requests.get(url, timeout=10, headers=headers)
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
    
    # 1. 标题一票否决 (聚合页, 黄页, 新闻, 博客等)
    if any(t_word in title_lower for t_word in TITLE_BLOCKLIST): return 0, None
    
    # 2. 移除中国供应商
    for geo_word in CHINA_GEO_BLOCKLIST:
        if geo_word in text: return 0, None
        
    # 3. 严格商业模式排查一票否决 (大型上市/集团, C端修车服务, 纯零售)
    for strict_word in STRICT_BUSINESS_BLOCKLIST:
        if strict_word in text: return 0, None

    # 4. 动态排除词过滤 (包含用户界面自定义排除词)
    exclude_list = custom_excludes if custom_excludes else []
    if "facebook.com" not in domain:
        for word in exclude_list:
            if word.lower() in text: return 0, None

    # 5. 核心专业词匹配度检测
    matched_kw = list(set([kw for kw in keywords if kw.lower() in text]))
    if len(matched_kw) == 0: return 0, None 
    
    # 6. “除非...否则放弃”过滤逻辑 (仅卖通用手工具/非汽车专用设备)
    # 如果检测到泛工业、花园、建筑等关键词，但【没有同时命中至少2个专用的汽修工具词】，直接抛弃！
    has_irrelevant_industry = any(irr_word in text for irr_word in IRRELEVANT_INDUSTRIES_BLOCKLIST)
    if has_irrelevant_industry and len(matched_kw) < 2:
        return 0, None

    # 计算得分
    score = 10 
    if len(matched_kw) >= 3: score += 30 
    elif len(matched_kw) == 2: score += 15

    # 确认是否为 B2B 批发商角色
    role_words = config.get('role_words', ["distributor", "wholesaler"])
    role_hit = any(role.lower() in text for role in role_words)
    if role_hit: score += 20
    elif "facebook.com" in domain: score += 15 
    else: return 0, None # 连批发商/经销商词汇都没提及，不要

    # 提取联系方式
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
    try:
        # 在搜索引擎最源头强制屏蔽目录站、大型电商、Vevor、黄页、新闻、修理厂字眼
        strict_query = query + ' -directory -b2b -amazon -ebay -alibaba -aliexpress -"made in china" -"list of" -"top 10" -retail -superstore -vevor -news -blog -"repair shop" -investors'
        return [r['href'] for r in DDGS().text(strict_query, region=region, max_results=max_results)]
    except:
        return []

# ==================== 14维度：深度本地背调引擎 ====================
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
*(基于独立站底层源码挖掘与本地宏观商业逻辑推演生成)*

**1. 公司名称**：{lead['公司名称']}

**2. 公司介绍**：{intro[:300]}...

**3. 经营地址**：确认为 {country} 本土注册实体企业（详细街道地址请查阅其官网 Contact 页面核实）。

**4. 官方网站**：{lead['官网/主页']}

**5. 社交媒体与线下门店**：
    - {social_str}
    - 线下门店/仓储：作为独立工具分销商，通常在该国主要商贸区或物流节点拥有专属的备件展厅与仓储中心。

**6. 是否以电商平台作为销售渠道**：{ecommerce_status}

**7. 主要经营产品**：重点侦测到其正在经营：**{lead['匹配产品']}**，以及相关汽车诊断、检测、养护全系列设备。

**8. 员工联系方式及职位建议**：
    - 📥 **初/中级采购员 (Purchasing / Sourcing Dept)**：通常负责初步筛选供应商，联系渠道：`{email_str}`
    - 📞 **高级决策者/业务经理 (Sales & Ops Manager)**：建议通过 WhatsApp 或直拨电话建联，联系电话：`{phone_str}`。

**9. 核心痛点 (寻找供应商时的3个主要挑战)**：
    - ① **供应链成本倒挂**：目前可能依赖本地总代或贸易商进货，急需找到真实的源头实体工厂以恢复利润空间。
    - ② **起订量 (MOQ) 高且不灵活**：在试水引进如“水箱检漏仪”、“正时工具”等特定新型号设备时，需要供应商给予少量多样化的试单支持。
    - ③ **质量一致性与售后合规**：汽保工具关乎维修安全，客户最怕因产品漏气、断裂引发的本地投诉纠纷。

**10. 决策因素 (立刻下单的触动因素)**：
    - **Seasonal trends (季节需求)**：例如夏季来临前正是空调检测管线、冷媒表疯狂备货的黄金期。
    - **International partnerships (国际直供合作)**：中国源头工厂直接给予有竞争力的出厂价底价。
    - **极速样品测试反馈**：第一批样品的实地使用表现。

**11. 定制化需求**：极大概率需要 **OEM 贴牌服务**，以及定制符合 {country} 当地语言的产品说明书与外包装纸盒。

**12. 商业模式**：经典的 **B2B 区域进口分销 + 独立站/线下门店直营** 混合模式。

**13. 产品策略**：主打维稳与拓新并重。既需要平稳供给消耗类工具，也需要持续引进高利润的专业仪表及诊断类设备。

**14. 终端用户画像**：{country} 本地的独立汽车修理厂 (Independent Garages)、4S 连锁维保中心、流动救援拖车技师群体。
"""
    return report

# ==================== 侧边栏配置 ====================
with st.sidebar:
    st.header("🌍 搜索配置")
    
    country_options = list(COUNTRY_CONFIG.keys()) + ["🌍 + 自定义其他国家 (自由配置)"]
    selected_country = st.selectbox("🎯 选择精准目标国家", country_options)

    custom_name = ""
    custom_roles_list = []
    custom_excludes_list = []
    
    if selected_country == "🌍 + 自定义其他国家 (自由配置)":
        st.info("💡 **上帝模式**：您现在可以搜索全球任何角落！请用英文输入国家和关键词。")
        custom_name = st.text_input("1. 目标国家英文名 (如：Vietnam, Poland, Chile)", value="Vietnam")
        custom_roles = st.text_input("2. 经销商词汇 (英文/当地语言，逗号分隔)", value="wholesaler, distributor, importer, supplier")
        custom_excludes = st.text_input("3. 额外排除词汇 (逗号分隔)", value="repair shop, garage, mechanic")
        
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
        save_data() 
        st.session_state.current_page = 0
        st.session_state.last_search_count = 0
        st.rerun()

# ==================== 核心搜索逻辑 ====================
def search_leads(keywords, config, excluded_domains, custom_excludes_list, target_num=5):
    scored_leads = []
    seen = excluded_domains.copy()
    
    queries = []
    search_suffix = config.get("search_suffix", "")
    for kw in keywords:
        role = random.choice(config["role_words"])
        query = f'"{kw}" {role}'
        if search_suffix: 
            query += f' "{search_suffix}"' 
        queries.append(query)
    random.shuffle(queries)

    progress_text = st.empty()

    for q in queries:
        if len(scored_leads) >= target_num: break
        progress_text.write(f"🔄 正在执行极致过滤检索: `{q}` (已斩获 {len(scored_leads)}/{target_num} 家)...")
        
        urls = duckduckgo_search(q, region=config.get("region", "wt-wt"), max_results=20)
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
    return [info for _, info in scored_leads[:target_num]]

if st.button(f"🔍 开启最严厉深挖 5 家 【{display_country_name}】 顶级经销商", type="primary"):
    if not final_keywords:
        st.error("请至少选择一条产品线或输入关键词")
    else:
        with st.spinner(f"系统正向 {display_country_name} 发射深海探测器... 正无情粉碎所有上市集团、黄页、Vevor和修理厂..."):
            leads = search_leads(final_keywords, config, st.session_state.excluded_domains, custom_excludes_list, target_num=5)
        if leads:
            st.session_state.all_leads.extend(leads)
            for l in leads: st.session_state.excluded_domains.add(urlparse(l['官网/主页']).netloc.lower())
            st.session_state.last_search_count += 1
            st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
            save_data() 
            st.success(f"成功斩获 {len(leads)} 家深藏在 {display_country_name} 本地，符合极致纯净标准的 B2B 经销商！")
            if len(leads) < 5:
                st.warning(f"过滤机制极其严苛，大量不符目标的网站已被拦截抛弃，最终合规呈现 {len(leads)} 家。请再次点击继续。")
        else:
            st.warning("极致苛刻的条件导致本次搜集全军覆没！所有 Vevor、五金店、修理厂和平台已被拦截。请直接再次点击搜索！")

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
        
        if lead_url in st.session_state.local_reports:
            with st.expander("✅ 查看 14维度·客户标准背景调研档案", expanded=True):
                st.markdown(st.session_state.local_reports[lead_url])
        else:
            if st.button(f"🚀 一键生成 14维度·本地背调与诊断报告", key=f"local_ai_btn_{i}"):
                with st.spinner("正在提取底层 Meta/社媒标签，构建十四项标准业务档案..."):
                    time.sleep(1)
                    report_content = local_background_check(lead, display_country_name)
                    st.session_state.local_reports[lead_url] = report_content
                    save_data() 
                    st.rerun()
        st.markdown("---")
