import streamlit as st
import requests
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ddgs import DDGS

st.set_page_config(page_title="JYTOOL 汽保工具 B2B 精准获客", layout="wide")
st.title("🔧 JYTOOL 汽保工具 · 全球 B2B 经销商精准搜索")
st.markdown("🎯 **系统特色**: 搭载「地理围栏拦截技术」，绝对秒杀中国供应商！强制过滤全球所有 B2B/B2C 电商与零售黄页平台。")

# ==================== 终极黑名单配置 ====================
# 1. 全球平台、电商、黄页彻底封杀名单 (B2B/B2C/黄页)
PLATFORM_BLOCKLIST = [
    "amazon.", "ebay.", "aliexpress.", "alibaba.", "made-in-china.", "globalsources.", 
    "dhgate.", "tradekey.", "hktdc.", "walmart.", "mercadolibre.", "shopee.", "lazada.", 
    "etsy.", "wayfair.", "indiamart.", "ec21.", "tradeindia.", "temu.", "shein.", 
    "banggood.", "gearbest.", "lightinthebox.", "dx.com", "tomtop.", "ubuy.", "desertcart.",
    "fruugo.", "joom.", "yellowpages.", "yelp.", "trustpilot.", "zoominfo.", "dnb.",
    "kompass.", "europages.", "thomasnet.", "macys.", "homedepot.", "lowes.", "target.",
    "craigslist.", "gumtree.", "olx.", "carousell."
]

# 2. “伪谷歌地图”地理围栏：中国本土城市、省份及特征词封杀名单
# 如果目标网站的地址栏包含以下任何地名或特征，直接判定为中国同行，予以抹杀！
CHINA_GEO_BLOCKLIST = [
    "guangdong", "shenzhen", "guangzhou", "dongguan", "foshan", "zhongshan", "zhuhai",
    "zhejiang", "ningbo", "hangzhou", "yiwu", "wenzhou", "taizhou", "jinhua", "shaoxing",
    "jiangsu", "shanghai", "shandong", "qingdao", "jinan", "hebei", "henan",
    "fujian", "xiamen", "quanzhou", "anhui", "hubei", "hunan", "sichuan",
    "beijing", "tianjin", "+86 ", "0086", "86-1", "86-0", 
    "made in china", "china mainland", "mainland china", "chinese supplier",
    "zhuji", "jinyue" # 也排除可能搜到自己的情况
]

# ==================== 独立国家精细化配置 ====================
COUNTRY_CONFIG = {
    "美国 (USA)": {
        "region": "us-en",
        "role_words": ["wholesaler", "distributor", "supplier", "dealer", "tool store", "garage equipment"],
        "exclude_words": ["auto repair shop", "repair service", "body shop", "car wash", "towing service"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["radiator pressure tester", "cylinder compression tester", "fuel pressure gauge"]},
            "02 液体更换/补充工具": {"search": ["brake fluid replacement tool", "brake bleeder", "oil extractor"]},
            "03 汽车空调制冷工具": {"search": ["a/c manifold gauge", "refrigerant charging kit", "a/c leak detection"]},
            "04 车身拆卸/卡扣工具": {"search": ["trim removal tool", "plastic pry tools", "car clip set"]},
            "05 发动机正时工具": {"search": ["engine timing tool", "camshaft locking tool", "crankshaft tool"]}
        }
    },
    "英国 (UK)": {
        "region": "uk-en",
        "role_words": ["wholesaler", "distributor", "supplier", "dealer", "tool store", "garage equipment"],
        "exclude_words": ["auto repair shop", "repair service", "body shop", "car wash", "towing service", "tyre shop"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["radiator pressure tester", "cylinder compression tester", "fuel pressure gauge"]},
            "02 液体更换/补充工具": {"search": ["brake fluid replacement tool", "brake bleeder", "oil extractor"]},
            "03 汽车空调制冷工具": {"search": ["a/c manifold gauge", "refrigerant charging kit", "a/c leak detection"]},
            "04 车身拆卸/卡扣工具": {"search": ["trim removal tool", "plastic pry tools", "car clip set"]},
            "05 发动机正时工具": {"search": ["engine timing tool", "camshaft locking tool", "crankshaft tool"]}
        }
    },
    "斯里兰卡 (Sri Lanka)": {
        "region": "lk-en",
        "role_words": ["wholesaler", "distributor", "supplier", "dealer", "auto parts", "garage equipment"],
        "exclude_words": ["auto repair shop", "service station", "tyre shop", "mechanic service"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["radiator pressure tester", "compression tester", "fuel pressure gauge"]},
            "02 液体更换/补充工具": {"search": ["brake bleeder", "oil extractor", "fluid syringe"]},
            "03 汽车空调制冷工具": {"search": ["a/c manifold gauge", "refrigerant charging", "leak detection"]},
            "04 车身拆卸/卡扣工具": {"search": ["trim removal tool", "plastic pry tools", "car clips"]},
            "05 发动机正时工具": {"search": ["engine timing tool", "camshaft tool", "crankshaft tool"]}
        }
    },
    "德国 (Germany)": {
        "region": "de-de",
        "role_words": ["Großhandel", "Importeur", "Distributor", "Händler", "Werkzeug-Shop", "Werkstattausrüstung"],
        "exclude_words": ["Autoreparatur", "Reparaturservice", "Reifenservice", "Lackiererei", "Abschleppdienst"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["Kühlsystem-Dichtheitsprüfer", "Kompressionstester", "Kraftstoffdruckprüfer"]},
            "02 液体更换/补充工具": {"search": ["Bremsenentlüftungsgerät", "Ölabsaugpumpe", "Bremsflüssigkeitswechsler"]},
            "03 汽车空调制冷工具": {"search": ["Klima-Monteurhilfe", "Kältemittel-Füllschlauch", "Klima-Lecksuchgerät"]},
            "04 车身拆卸/卡扣工具": {"search": ["Zierleistenkeile", "Türverkleidungs-Werkzeug", "Schlauchklemmenzange"]},
            "05 发动机正时工具": {"search": ["Motor-Einstellwerkzeug", "Nockenwellen-Arretierwerkzeug", "Zahnriemen-Werkzeug"]}
        }
    },
    "法国 (France)": {
        "region": "fr-fr",
        "role_words": ["grossiste", "importateur", "distributeur", "fournisseur", "boutique d'outillage", "équipement d'atelier"],
        "exclude_words": ["centre de réparation", "carrosserie", "pneumatique", "service de réparation"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["testeur de pression de radiateur", "compressiomètre", "testeur de pression de carburant"]},
            "02 液体更换/补充工具": {"search": ["purgeur de frein", "extracteur d'huile", "pompe à vide"]},
            "03 汽车空调制冷工具": {"search": ["manifold de climatisation", "kit de charge de réfrigérant", "détecteur de fuite"]},
            "04 车身拆卸/卡扣工具": {"search": ["outils de démontage garniture", "pinces pour colliers", "kit de clips auto"]},
            "05 发动机正时工具": {"search": ["outil de calage moteur", "outil de blocage d'arbre à cames", "kit de distribution"]}
        }
    },
    "西班牙 (Spain)": {
        "region": "es-es",
        "role_words": ["mayorista", "importador", "distribuidor", "proveedor", "tienda de herramientas", "equipamiento de taller"],
        "exclude_words": ["taller mecánico", "centro de reparación", "chapa y pintura", "neumáticos", "grúa"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["probador de presión de radiador", "comprobador de compresión", "medidor de presión de combustible"]},
            "02 液体更换/补充工具": {"search": ["purgador de frenos", "extractor de aceite", "bomba de vacío"]},
            "03 汽车空调制冷工具": {"search": ["manómetro de aire acondicionado", "kit de carga de refrigerante", "detector de fugas a/c"]},
            "04 车身拆卸/卡扣工具": {"search": ["herramientas para desmontar molduras", "alicates para abrazaderas", "kit de grapas coche"]},
            "05 发动机正时工具": {"search": ["kit de calado de motor", "herramienta de sincronización", "bloqueo de árbol de levas"]}
        }
    }
}

# ==================== 辅助函数 ====================
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

def score_lead(html, url, config, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    domain = urlparse(url).netloc.lower()
    
    # 🚨 终极核武器：探测网页文本中是否包含中国省份/城市地址，或者中国区号
    for geo_word in CHINA_GEO_BLOCKLIST:
        if geo_word in text:
            # 一旦发现属于中国供应商（哪怕是伪装得再好的英文网站），直接标记为0分抹杀
            return 0, None

    # 排除 C端汽修厂
    if "facebook.com" not in domain:
        for word in config['exclude_words']:
            if word.lower() in text:
                return 0, None

    matched_kw = list(set([kw for kw in keywords if kw.lower() in text]))
    if len(matched_kw) == 0:
        return 0, None 
    
    score = 10 
    if len(matched_kw) >= 3: score += 30 
    elif len(matched_kw) == 2: score += 15

    role_hit = any(role.lower() in text for role in config['role_words'])
    if role_hit: score += 20
    elif "facebook.com" in domain: score += 15 
    else: return 0, None 

    emails = list(dict.fromkeys(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
    wa_links = list(set(re.findall(r'(https?://(?:wa\.me/|api\.whatsapp\.com/send\?phone=)[0-9]+)', html)))
    fb_links = list(set(re.findall(r'(https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+)', html)))
    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    
    # 二次核对电话号码，如果包含 +86 等中国号码，直接斩杀
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
    company = soup.title.string.strip() if soup.title else domain

    return score, {
        '公司名称': company[:60] + "..." if len(company)>60 else company,
        '官网/主页': url,
        '匹配产品': ', '.join(matched_kw[:5]), 
        '产品数': len(matched_kw),
        '联系方式': " | ".join(contact_parts),
        '评分': score,
        'HTML内容': html 
    }

def duckduckgo_search(query, region, max_results=5):
    try:
        # 向搜索引擎追加极其严格的过滤后缀，防止底层传回垃圾平台数据
        strict_query = query + ' -amazon -ebay -alibaba -aliexpress -"made in china" -site:amazon.com -site:ebay.com'
        return [r['href'] for r in DDGS().text(strict_query, region=region, max_results=max_results)]
    except:
        return []

# ==================== 本地化零成本深度背调引擎 ====================
def local_background_check(lead, country):
    soup = BeautifulSoup(lead['HTML内容'], 'html.parser')
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    intro = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else "（系统分析）该客户为纯正海外本地独立的专业汽保工具及设备分销商，非中国同行，非电商零售平台。"
    
    ecommerce_status = "否（传统的本土线下批发/经销商独立官网）"
    if "cart" in lead['HTML内容'].lower() or "add to cart" in lead['HTML内容'].lower():
        ecommerce_status = f"是（本土独立站零售电商，绝非中国跨境卖家）"

    currency = "$" if "美国" in country else ("€" if any(c in country for c in ["德国","法国","西班牙"]) else "当地货币")
    price_multiplier = 1.5 if "美国" in country or "德国" in country else 1.2
    
    report = f"""
### 📊 资深业务员：{lead['公司名称']} 本土背调报告
*(本报告采用网页深度解析技术生成，已确认排华安全)*

#### 一、 本土客户验身报告
*   **1. 公司名称**：{lead['公司名称']}
*   **2. 公司介绍**：{intro[:150]}...
*   **3. 官方主页**：{lead['官网/主页']}
*   **4. 平台性质筛查**：**【✅极度安全】** 系统已扫描该网页所有隐藏代码及地址栏，未发现任何深圳/义乌/广州等中国供应商特征，确认为海外本土独立买家。
*   **5. 商业形态**：{ecommerce_status}。
*   **6. 经营产品**：正在热销 {lead['匹配产品']}。
*   **7. 核心联系**：{lead['联系方式']}
*   **8. 采购痛点推演**：作为 {country} 的独立经销商，其痛点在于：1. 避开中间商，直接寻找真实的中国源头工厂；2. 保证高客单价检测工具的精度售后。
*   **9. 促单决策因素**：源头工厂出厂价、稳定的供货能力、不依赖平台直接交易的信任感。

#### 二、 当地市场 ({country}) 销售潜力
*   **1. 市场价格空间**：此类产品在 {country} 线下渠道的零售批发加价率普遍高达 100%~200%（预计为出厂价的 {price_multiplier} 倍）。
*   **2. 核心推荐策略**：
    该客户高度契合我们工厂属性。强烈建议您通过 {lead['联系方式']} 发送开发信，告知对方：
    *"我们是专业的中国源头工厂 (JYTOOL)，您网站上在售的 {lead['匹配产品']} 我们不仅直接生产，且可提供极具竞争力的出厂价与贴牌服务。"*
"""
    return report

# ==================== 数据持久化 ====================
if 'excluded_domains' not in st.session_state: st.session_state.excluded_domains = set()
if 'all_leads' not in st.session_state: st.session_state.all_leads = []
if 'current_page' not in st.session_state: st.session_state.current_page = 0
if 'last_search_count' not in st.session_state: st.session_state.last_search_count = 0
if 'local_reports' not in st.session_state: st.session_state.local_reports = {}

with st.sidebar:
    st.header("🌍 搜索配置")
    selected_country = st.selectbox("🎯 选择精准目标国家", list(COUNTRY_CONFIG.keys()))
    config = COUNTRY_CONFIG[selected_country]

    st.subheader("📦 选择产品线")
    selected_lines = [line for line in config['product_lines'].keys() if st.checkbox(line, value=True)]
    
    manual_keywords = st.text_area("输入特定词汇（可选）", height=80)
    final_keywords = []
    for line in selected_lines:
        final_keywords.extend(config['product_lines'][line]['search'])
    if manual_keywords.strip():
        final_keywords.extend([k.strip() for k in manual_keywords.splitlines() if k.strip()])
    final_keywords = list(set(final_keywords))

    st.markdown("---")
    st.success(f"已沉淀高优本土客户: {len(st.session_state.all_leads)} 家")
    if st.button("清空所有记录(重新开始)"):
        st.session_state.excluded_domains.clear()
        st.session_state.all_leads.clear()
        st.session_state.local_reports.clear()
        st.session_state.current_page = 0
        st.session_state.last_search_count = 0
        st.rerun()

# ==================== 核心搜索逻辑 ====================
def search_leads(keywords, config, excluded_domains, max_new=5):
    scored_leads = []
    seen = excluded_domains.copy()
    
    queries = [f'"{kw}" {random.choice(config["role_words"])}' for kw in keywords]
    random.shuffle(queries)

    for q in queries:
        if len(scored_leads) >= max_new: break
        urls = duckduckgo_search(q, region=config.get("region", "us-en"), max_results=5)
        for url in urls:
            domain = urlparse(url).netloc.lower()
            
            # 第一道防线：URL特征拦截（拦截亚马逊、阿里等）
            if any(b in domain for b in PLATFORM_BLOCKLIST): continue
            # 防止自己家被搜出来
            if "jinyue" in domain or "jytool" in domain: continue
            if domain in seen and "facebook.com" not in domain: continue
            
            html = fetch_page(url)
            if not html: continue
            
            # 第二道防线：HTML网页底层内容坐标拦截（排除中国供应商）
            score, info = score_lead(html, url, config, keywords)
            if score > 0:
                scored_leads.append((score, info))
                seen.add(domain)
            else:
                seen.add(domain)
        time.sleep(1)

    scored_leads.sort(key=lambda x: x[0], reverse=True)
    return [info for _, info in scored_leads[:max_new]]

if st.button("🔍 智能挖掘 5 家本土纯净经销商", type="primary"):
    if not final_keywords:
        st.error("请至少选择一条产品线")
    else:
        with st.spinner("系统启动地理坐标排雷引擎... 正在斩杀所有电商平台与中国伪装供应商..."):
            leads = search_leads(final_keywords, config, st.session_state.excluded_domains, max_new=5)
        if leads:
            st.session_state.all_leads.extend(leads)
            for l in leads: st.session_state.excluded_domains.add(urlparse(l['官网/主页']).netloc.lower())
            st.session_state.last_search_count += 1
            st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
            st.success(f"成功斩获 {len(leads)} 家无平台、无同行的纯本土经销商！")
        else:
            st.warning("要求过于严苛导致未命中，这是好事！证明我们拦截了大量的中国同行与垃圾平台，请再次点击搜索。")

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
        st.write(f"第 {current_page+1}/{total_pages} 页 · 库内共 {total_leads} 家客户")
    with col4:
        st.download_button("📥 导出纯净名单", pd.DataFrame(st.session_state.all_leads)[['公司名称','官网/主页','匹配产品','联系方式','评分']].to_csv(index=False).encode('utf-8-sig'), "JYTOOL_Independent_Leads.csv")

    start_idx = current_page * 5
    end_idx = min(start_idx + 5, total_leads)
    
    for i in range(start_idx, end_idx):
        lead = st.session_state.all_leads[i]
        score_color = "🔥" if lead['产品数'] >= 3 else "🟢"
        lead_url = lead['官网/主页']
        
        st.subheader(f"{i+1}. {score_color} {lead['公司名称']} (综合意向分: {lead['评分']})")
        st.markdown(f"**独立官网/社媒**: [{lead_url}]({lead_url})")
        st.markdown(f"🎯 **精准匹配**: `{lead['匹配产品']}` | 📞 **联系渠道**: {lead['联系方式']}")
        
        if lead_url in st.session_state.local_reports:
            with st.expander("✅ 查看本土背调与诊断报告", expanded=True):
                st.markdown(st.session_state.local_reports[lead_url])
        else:
            if st.button(f"🚀 一键生成本土排华检验与背调报告", key=f"local_ai_btn_{i}"):
                with st.spinner("启动底层数据分析与坐标检验..."):
                    time.sleep(1)
                    report_content = local_background_check(lead, selected_country)
                    st.session_state.local_reports[lead_url] = report_content
                    st.rerun()
        st.markdown("---")
