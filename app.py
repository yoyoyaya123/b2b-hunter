import streamlit as st
import requests
import re
import csv
import time
import random
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO

st.set_page_config(page_title="外贸B2B搜客", layout="wide")
st.title("🔧 汽车维修专用工具 · B2B精准客户搜索")

# ---- 侧边栏配置 ----
with st.sidebar:
    st.header("搜索设置")
    target_country = st.text_input("目标国家", "Deutschland")
    target_cities = st.text_input("优先城市（逗号分隔）", "Berlin, Hamburg, München")
    max_results = st.slider("每个关键词搜索数量", 5, 20, 10)
    delay = st.slider("访问间隔(秒)", 3, 15, 5)

    st.markdown("---")
    st.subheader("搜索策略（产品词+角色词）")
    strategy_a = st.text_area("A. 空调/冷却工具", "Kühlsystem-Dichtheitsprüfer Großhandel\nKlimaservice-Werkzeug Importeur")
    strategy_b = st.text_area("B. 仪表检测工具", "Zylinderdruckprüfer Großhandel\nKraftstoffdruckmessgerät Distributor\nDieseleinspritzung-Tester Importeur")
    strategy_c = st.text_area("C. 刹车/底盘工具", "Bremskolbenrückstellsatz Händler\nFahrwerk-Reparaturwerkzeug Lieferant\nKugelgelenkabzieher Großhandel")
    strategy_d = st.text_area("D. 液体更换设备", "Bremsenentlüftungsgerät Großhandel\nKühlmittel-Befüllset Importeur")
    strategy_e = st.text_area("E. 内饰/撬棒耗材", "Kunststoff-Nylon-Hebel-Set Distributor\nAuto-Clip-Set Lieferant")

    # 固定证据词和排除词（也可做成文本框，这里默认）
    st.markdown("---")
    st.caption("产品证据词与排除规则已内置，符合你提供的筛选标准")

# ---- 核心函数 ----
PRODUCT_EVIDENCE = [
    "Bremskolbenrückstellsatz", "Zylinderdruckprüfer", "Klimaservice-Werkzeug",
    "Bremsenentlüftungsgerät", "Kraftstoffdruckmessgerät", "Kühlsystem-Dichtheitsprüfer",
    "Dieseleinspritzung-Tester", "Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set",
    "Kugelgelenkabzieher", "Kupplungszentrierwerkzeug", "Bremsflüssigkeitswechsler",
]

EXCLUDE_KEYWORDS = [
    "Werkstatt", "Reparatur", "Service-Center", "Autohaus", "Reifenservice",
    "Karosseriebau", "Lackiererei", "Tuning", "Industrie", "Baumaschinen",
    "Gartengeräte", "Landwirtschaft",
]

ROLE_KEYWORDS = [
    "Großhandel", "Großhändler", "Importeur", "Import", "Distributor",
    "Händler", "Lieferant", "Fachhandel", "Wiederverkäufer", "Exporteur",
]

@st.cache_data
def fetch_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, timeout=10, headers=headers)
        resp.raise_for_status()
        return resp.text
    except:
        return None

def contains_any(text, kw_list):
    text = text.lower()
    return any(kw.lower() in text for kw in kw_list)

def extract_info(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()

    # 排除
    if contains_any(text, EXCLUDE_KEYWORDS):
        return None
    if not contains_any(text, ROLE_KEYWORDS):
        return None
    if not contains_any(text, PRODUCT_EVIDENCE):
        return None

    domain = urlparse(url).netloc
    company = soup.title.string.strip() if soup.title else domain

    # 邮箱
    emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
    emails = [e for e in emails if 'noreply' not in e and 'example' not in e]

    # 社媒链接
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
    text_lower = text.lower()
    if 'familienbetrieb' in text_lower or 'inhabergeführt' in text_lower:
        scale = "家族式中小型"
    elif 'mitarbeiter' in text_lower:
        scale = "推测中小型"
    else:
        scale = "中小型（未发现大型特征）"

    # 电商
    ecommerce = []
    if 'amazon.de' in html:
        ecommerce.append("Amazon")
    if 'ebay.de' in html:
        ecommerce.append("eBay")
    ecommerce_str = ", ".join(ecommerce) if ecommerce else "未发现"

    # 电话
    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    contact = "邮箱: " + (", ".join(emails) if emails else "无") + "; 电话: " + (phones[0] if phones else "官网表单")

    # 匹配产品
    matched = [kw for kw in PRODUCT_EVIDENCE if kw.lower() in text.lower()]

    return {
        '公司名称': company,
        '官网': url,
        '匹配产品': ', '.join(matched[:3]) if matched else "",
        '社媒': socials,
        '规模': scale,
        '电商渠道': ecommerce_str,
        '联系方式': contact,
    }

def search_google(query, num):
    try:
        from googlesearch import search
        return list(search(query, num=num, stop=num, user_agent='Mozilla/5.0', lang='de', country='de'))
    except:
        st.warning(f"Google搜索暂时受限: {query}")
        return []

# ---- 主界面 ----
if st.button("🚀 开始搜索", type="primary"):
    cities = [c.strip() for c in target_cities.split(",") if c.strip()]
    strategies = {
        "A.空调冷却": [l.strip() for l in strategy_a.splitlines() if l.strip()],
        "B.仪表检测": [l.strip() for l in strategy_b.splitlines() if l.strip()],
        "C.刹车底盘": [l.strip() for l in strategy_c.splitlines() if l.strip()],
        "D.液体更换": [l.strip() for l in strategy_d.splitlines() if l.strip()],
        "E.内饰耗材": [l.strip() for l in strategy_e.splitlines() if l.strip()],
    }

    all_leads = []
    seen = set()
    progress_bar = st.progress(0)
    status = st.empty()

    total_queries = sum(len(qs) for qs in strategies.values())
    current_query = 0

    for strat_name, queries in strategies.items():
        for base_query in queries:
            # 动态加入城市
            for city in cities:
                full_query = f"{base_query} {city}" if city else base_query
                current_query += 1
                status.text(f"正在搜索: {full_query} ({current_query}/{total_queries * len(cities)})")
                progress_bar.progress(min(current_query / (total_queries * len(cities)), 1.0))

                results = search_google(full_query, max_results)
                for url in results:
                    domain = urlparse(url).netloc
                    if domain in seen:
                        continue
                    seen.add(domain)
                    html = fetch_page(url)
                    if not html:
                        continue
                    info = extract_info(html, url)
                    if info:
                        all_leads.append(info)
                    time.sleep(random.uniform(delay * 0.5, delay))
            time.sleep(3)

    progress_bar.empty()
    status.empty()

    if not all_leads:
        st.warning("未找到完全匹配的公司，请放宽条件或更换城市重试。")
    else:
        # 去重并取前5
        unique = []
        seen_names = set()
        for lead in all_leads:
            if lead['公司名称'] not in seen_names:
                seen_names.add(lead['公司名称'])
                unique.append(lead)
        final = unique[:5]

        st.success(f"找到 {len(unique)} 家匹配公司，展示前5家。")

        # 卡片展示
        for i, lead in enumerate(final, 1):
            with st.container():
                st.subheader(f"{i}. {lead['公司名称']}")
                st.markdown(f"**官网**: [{lead['官网']}]({lead['官网']})")

                social_links = []
                for name, link in lead['社媒']:
                    if name and link.startswith('http'):
                        social_links.append(f"[{name}]({link})")
                    elif link == "未找到公开社媒":
                        social_links.append("未找到公开社媒")
                    else:
                        social_links.append(link)
                st.markdown(f"**社媒**: {' · '.join(social_links)}")

                st.markdown(f"**匹配产品**: {lead['匹配产品']}")
                st.markdown(f"**规模**: {lead['规模']}  |  **电商**: {lead['电商渠道']}")
                st.markdown(f"**联系方式**: {lead['联系方式']}")
                st.markdown("---")

        # 导出按钮
        df = pd.DataFrame(final)
        # 社媒列转为字符串以便CSV导出
        df['社媒'] = df['社媒'].apply(lambda x: '; '.join([f"{n}: {l}" for n, l in x]) if isinstance(x, list) else x)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下载Excel/CSV",
            data=csv,
            file_name='leads.csv',
            mime='text/csv',
        )