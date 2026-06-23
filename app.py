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
st.markdown("🎯 **特色**: 自动屏蔽中国同行、数据持久去重保存、生成 0 成本高阶 AI 调研指令（支持亚马逊中国卖家排查）。")

# ==================== 黑名单配置 (屏蔽中国网站) ====================
CHINA_BLOCKLIST = [
    ".cn", ".com.cn", ".tw", ".hk", 
    "alibaba.com", "aliexpress.com", "1688.com", "taobao.com", "jd.com", 
    "made-in-china.com", "globalsources.com", "dhgate.com", "chinabrands.com",
    "tradekey.com", "hktdc.com"
]

# ==================== 全球语言区配置 ====================
COUNTRY_CONFIG = {
    "英国/美国/斯里兰卡等(英文区)": {
        "region": "us-en",
        "cities": ["London", "New York", "Los Angeles", "Colombo", "Sydney"],
        "role_words": ["wholesaler", "distributor", "supplier", "dealer", "tool store", "garage equipment", "diagnostic"],
        "exclude_words": ["auto repair shop", "repair service", "body shop", "car wash", "towing service"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["radiator pressure tester", "cylinder compression tester", "fuel pressure gauge"]},
            "02 液体更换/补充工具": {"search": ["brake fluid replacement tool", "brake bleeder", "oil extractor"]},
            "03 汽车空调制冷工具": {"search": ["a/c manifold gauge", "refrigerant charging kit", "a/c leak detection"]},
            "04 车身拆卸/卡扣工具": {"search": ["trim removal tool", "plastic pry tools", "car clip set"]},
            "05 发动机正时工具": {"search": ["engine timing tool", "camshaft locking tool", "crankshaft tool"]}
        }
    },
    "德国 (德语区)": {
        "region": "de-de",
        "cities": ["Berlin", "Hamburg", "München", "Frankfurt", "Stuttgart"],
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
    "西班牙/南美 (西语区)": {
        "region": "es-es",
        "cities": ["Madrid", "Barcelona", "Caracas", "Valencia", "Bogotá"],
        "role_words": ["mayorista", "importador", "distribuidor", "proveedor", "tienda de herramientas", "equipamiento de taller"],
        "exclude_words": ["taller mecánico", "centro de reparación", "chapa y pintura", "neumáticos", "servicio mecánico", "grúa"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["probador de presión de radiador", "comprobador de compresión", "medidor de presión de combustible"]},
            "02 液体更换/补充工具": {"search": ["purgador de frenos", "extractor de aceite", "bomba de vacío", "cambio de líquido de frenos"]},
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
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(url, timeout=10, headers=headers)
            resp.raise_for_status()
            return resp.text
        except:
            time.sleep(1)
    return None

def score_lead(html, url, config, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    domain = urlparse(url).netloc
    
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
        '评分': score
    }

def duckduckgo_search(query, region, max_results=5):
    try:
        return [r['href'] for r in DDGS().text(query, region=region, max_results=max_results)]
    except:
        return []

# ==================== 数据与状态持久化 ====================
if 'excluded_domains' not in st.session_state: st.session_state.excluded_domains = set()
if 'all_leads' not in st.session_state: st.session_state.all_leads = []
if 'current_page' not in st.session_state: st.session_state.current_page = 0
if 'last_search_count' not in st.session_state: st.session_state.last_search_count = 0

with st.sidebar:
    st.header("🌍 搜索配置")
    selected_country = st.selectbox("选择目标语言区", list(COUNTRY_CONFIG.keys()))
    config = COUNTRY_CONFIG[selected_country]

    st.subheader("📦 选择我们的产品线")
    selected_lines = [line for line in config['product_lines'].keys() if st.checkbox(line, value=True)]
    
    manual_keywords = st.text_area("输入特定词汇（可选）", height=80)
    final_keywords = []
    for line in selected_lines:
        final_keywords.extend(config['product_lines'][line]['search'])
    if manual_keywords.strip():
        final_keywords.extend([k.strip() for k in manual_keywords.splitlines() if k.strip()])
    final_keywords = list(set(final_keywords))

    st.markdown("---")
    st.success(f"已沉淀客户数据: {len(st.session_state.all_leads)} 家")
    if st.button("清空所有记录(重新开始)"):
        st.session_state.excluded_domains.clear()
        st.session_state.all_leads.clear()
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
            if any(b in domain for b in CHINA_BLOCKLIST): continue
            if domain in seen and "facebook.com" not in domain: continue
            
            html = fetch_page(url)
            if not html: continue
            
            score, info = score_lead(html, url, config, keywords)
            if score > 0:
                scored_leads.append((score, info))
                seen.add(domain)
            else:
                seen.add(domain)
        time.sleep(1)

    scored_leads.sort(key=lambda x: x[0], reverse=True)
    return [info for _, info in scored_leads[:max_new]]

if st.button("🔍 挖掘 5 家全新经销商", type="primary"):
    if not final_keywords:
        st.error("请至少选择一条产品线")
    else:
        with st.spinner("系统正在全球扫描，已自动开启排华与历史去重机制..."):
            leads = search_leads(final_keywords, config, st.session_state.excluded_domains, max_new=5)
        if leads:
            st.session_state.all_leads.extend(leads)
            for l in leads: st.session_state.excluded_domains.add(urlparse(l['官网/主页']).netloc.lower())
            st.session_state.last_search_count += 1
            st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
            st.success(f"新增 {len(leads)} 家精准客户（累计 {len(st.session_state.all_leads)} 家）")
        else:
            st.warning("暂未发现有效客户，系统可能需要更多时间或请尝试更换国家区。")

# ==================== 分页与零成本背调提示词 ====================
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
        st.download_button("📥 导出全部客户 CSV", pd.DataFrame(st.session_state.all_leads).to_csv(index=False).encode('utf-8-sig'), "JYTOOL_Global_Leads.csv")

    start_idx = current_page * 5
    end_idx = min(start_idx + 5, total_leads)
    
    for i in range(start_idx, end_idx):
        lead = st.session_state.all_leads[i]
        score_color = "🔥" if lead['产品数'] >= 3 else "🟢"
        lead_url = lead['官网/主页']
        
        st.subheader(f"{i+1}. {score_color} {lead['公司名称']} (综合评分: {lead['评分']})")
        st.markdown(f"**官网/主页**: [{lead_url}]({lead_url})")
        st.markdown(f"🎯 **匹配产品**: `{lead['匹配产品']}` | 📞 **联系方式**: {lead['联系方式']}")
        
        # === 零成本：一键复制给免费版 AI 的提示词 ===
        with st.expander("🤖 0成本：获取 AI 深度背调专属指令"):
            st.info("💡 **操作指南**：点击代码框右上角的【复制图标】，将下方内容直接发给 **DeepSeek网页版、Kimi 或 ChatGPT(免费版)** 即可获取深度报告！")
            
            prompt_text = f"""您是一位资深且顶尖的外贸业务员，你要帮助我进行全世界网络的深度搜索并进行深度思考。

任务：
一.根据我提供的客户公司的部分信息，帮我通过互联网检索并调研客户的完整公司信息，包括：
1.公司名称、2.公司介绍、3.经营地址、4.官方网站
5.Facebook/Insgram/领英(账号名称和网址；线下门店名称和地址)
6.电商平台(亚马逊等)渠道。
【极其重要】：如果有亚马逊等电商平台店铺，请必须深度核实是否为中国跨境卖家同行（判断依据：发货地是否在国内、公司名是否含拼音/Shenzhen/Guangzhou/Trading/Ltd等特征）。如果是中国卖家，请醒目标记【🚨注意：此客户可能是中国跨境卖家同行，不建议开发】；如果是真实的海外本土商家，请标记【✅优质海外本土商家】。
7.主要经营产品
8.公司员工的Whatsapp/邮箱联系方式（涵盖初中高级决策者）
9.核心痛点:寻找供应商时面临的3个主要挑战
10.决策因素:哪些因素会让他们立刻下单？
11.定制化需求、12.商业模式、13.产品策略、14.终端用户画像

二.结合我方供应信息，深度思考：
1.该产品在当地市场的批发和零售价格
2.近三年每个月的销售数据(合理预估或调取宏观数据)
3.未来三年销售趋势分析
4.交叉推荐策略：还可以推荐我方目录中的哪些产品？

【目标客户初始信息】
公司名称：{lead['公司名称']}
官方网站：{lead_url}
已提取的联系方式：{lead['联系方式']}
我们侦测到他经营的产品：{lead['匹配产品']}

【我方供应信息】
中国诸暨金越五金工具 (JYTOOL)，主营：01仪表检测工具(水箱漏测仪等)、02液体更换工具(刹车油更换机等)、03空调制冷工具(冷媒表等)、04车身拆卸卡扣、05发动机正时工具。

请使用专业外贸术语，输出排版清晰的背调报告。"""
            
            st.code(prompt_text, language="markdown")
        st.markdown("---")
