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
st.markdown("🎯 **搜索逻辑**: 针对全球汽保设备经销商、工具专卖店。只要目标网站包含我们目录中的 **1~3 款** 核心产品，即判定为高意向潜客！")

# ==================== 全球9国产品线配置 (严格对齐JYTOOL PDF目录) ====================
COUNTRY_CONFIG = {
    "英国/美国/斯里兰卡等(英文区)": {
        "region": "us-en",
        "cities": ["London", "New York", "Los Angeles", "Colombo", "Sydney", "Dubai", "Johannesburg"],
        "role_words": ["wholesaler", "distributor", "supplier", "dealer", "tool store", "garage equipment", "auto parts", "diagnostic"],
        "exclude_words": ["auto repair shop", "repair service", "body shop", "car wash", "towing service", "oil change", "mobile mechanic"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["radiator pressure tester", "cylinder compression tester", "fuel pressure gauge", "oil pressure gauge", "vacuum gauge"]},
            "02 液体更换/补充工具": {"search": ["brake fluid replacement tool", "brake bleeder", "oil extractor", "fluid syringe", "vacuum pump"]},
            "03 汽车空调制冷工具": {"search": ["a/c manifold gauge", "refrigerant charging kit", "a/c leak detection", "valve core remover"]},
            "04 车身拆卸/卡扣工具": {"search": ["trim removal tool", "plastic pry tools", "car clip set", "hose clamp pliers", "bearing removal tool"]},
            "05 发动机正时工具": {"search": ["engine timing tool", "camshaft locking tool", "crankshaft tool"]}
        }
    },
    "德国 (德语区)": {
        "region": "de-de",
        "cities": ["Berlin", "Hamburg", "München", "Frankfurt", "Stuttgart"],
        "role_words": ["Großhandel", "Importeur", "Distributor", "Händler", "Werkzeug-Shop", "Werkstattausrüstung"],
        "exclude_words": ["Autoreparatur", "Reparaturservice", "Reifenservice", "Lackiererei", "Abschleppdienst"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["Kühlsystem-Dichtheitsprüfer", "Kompressionstester", "Kraftstoffdruckprüfer", "Öldruckprüfer"]},
            "02 液体更换/补充工具": {"search": ["Bremsenentlüftungsgerät", "Ölabsaugpumpe", "Bremsflüssigkeitswechsler", "Vakuumpumpe"]},
            "03 汽车空调制冷工具": {"search": ["Klima-Monteurhilfe", "Kältemittel-Füllschlauch", "Klima-Lecksuchgerät", "Ventilausdreher"]},
            "04 车身拆卸/卡扣工具": {"search": ["Zierleistenkeile", "Türverkleidungs-Werkzeug", "Schlauchklemmenzange", "Auto-Clip-Set"]},
            "05 发动机正时工具": {"search": ["Motor-Einstellwerkzeug", "Nockenwellen-Arretierwerkzeug", "Zahnriemen-Werkzeug"]}
        }
    },
    "法国 (法语区)": {
        "region": "fr-fr",
        "cities": ["Paris", "Lyon", "Marseille", "Lille", "Bordeaux"],
        "role_words": ["grossiste", "importateur", "distributeur", "fournisseur", "boutique d'outillage", "équipement d'atelier"],
        "exclude_words": ["centre de réparation", "carrosserie", "pneumatique", "service de réparation", "dépannage"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["testeur de pression de radiateur", "compressiomètre", "testeur de pression de carburant"]},
            "02 液体更换/补充工具": {"search": ["purgeur de frein", "extracteur d'huile", "pompe à vide", "remplacement de liquide de frein"]},
            "03 汽车空调制冷工具": {"search": ["manifold de climatisation", "kit de charge de réfrigérant", "détecteur de fuite de clim"]},
            "04 车身拆卸/卡扣工具": {"search": ["outils de démontage garniture", "pinces pour colliers", "kit de clips auto", "extracteur de roulement"]},
            "05 发动机正时工具": {"search": ["outil de calage moteur", "outil de blocage d'arbre à cames", "kit de distribution"]}
        }
    },
    "西班牙/委内瑞拉 (西语区)": {
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
    },
    "葡萄牙/巴西 (葡语区)": {
        "region": "pt-pt",
        "cities": ["Lisboa", "Porto", "São Paulo", "Rio de Janeiro"],
        "role_words": ["grossista", "importador", "distribuidor", "fornecedor", "loja de ferramentas", "equipamento de oficina"],
        "exclude_words": ["oficina mecânica", "centro de reparação", "bate-chapa", "pneus", "serviço de reboque"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["teste de pressão do radiador", "testador de compressão", "medidor de pressão de combustível"]},
            "02 液体更换/补充工具": {"search": ["sangrador de freios", "extrator de óleo", "bomba de vácuo", "troca de fluido de freio"]},
            "03 汽车空调制冷工具": {"search": ["manifold ar condicionado", "kit de recarga de refrigerante", "detector de vazamento a/c"]},
            "04 车身拆卸/卡扣工具": {"search": ["ferramentas de remoção de painel", "alicate de abraçadeira", "kit de grampos automotivos"]},
            "05 发动机正时工具": {"search": ["ferramenta de ponto do motor", "ferramenta de sincronismo", "trava do comando de válvulas"]}
        }
    },
    "意大利 (意语区)": {
        "region": "it-it",
        "cities": ["Milano", "Roma", "Napoli", "Torino", "Bologna"],
        "role_words": ["grossista", "importatore", "distributore", "fornitore", "negozio di utensili", "attrezzatura per officina"],
        "exclude_words": ["officina meccanica", "centro riparazioni", "carrozzeria", "gommista", "soccorso stradale"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["tester pressione radiatore", "tester di compressione", "manometro pressione carburante"]},
            "02 液体更换/补充工具": {"search": ["spurgo freni", "estrattore olio", "pompa del vuoto", "sostituzione liquido freni"]},
            "03 汽车空调制冷工具": {"search": ["gruppo manometrico a/c", "kit ricarica refrigerante", "rilevatore perdite a/c"]},
            "04 车身拆卸/卡扣工具": {"search": ["utensili rimozione pannelli", "pinza per fascette", "kit clip auto"]},
            "05 发动机正时工具": {"search": ["attrezzo fasatura motore", "bloccaggio albero a camme", "kit distribuzione"]}
        }
    }
}

# ==================== 辅助函数 ====================
def fetch_page(url, retries=2):
    for attempt in range(retries):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0.0.0 Safari/537.36'}
            resp = requests.get(url, timeout=12, headers=headers)
            resp.raise_for_status()
            return resp.text
        except:
            time.sleep(1)
    return None

def score_lead(html, url, config, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    
    # 1. 排除纯B2C修车店（但如果是Facebook工具卖家的主页则网开一面）
    domain = urlparse(url).netloc
    if "facebook.com" not in domain:
        for word in config['exclude_words']:
            if word.lower() in text:
                return 0, None

    # 2. 产品关键词匹配 (核心逻辑：存在2-3件即可)
    matched_kw = list(set([kw for kw in keywords if kw.lower() in text]))
    if len(matched_kw) == 0:
        return 0, None  # 一件都没命中，放弃
    
    score = 10  # 基础分
    
    # 【亮点】命中多款产品加分算法：体现该网站是一个综合经销商
    if len(matched_kw) >= 3:
        score += 30  # 极大概率是对口五金/工具分销商
    elif len(matched_kw) == 2:
        score += 15

    # 3. 角色词或社媒属性命中 (如 Digitzone 是个经销商)
    role_hit = any(role.lower() in text for role in config['role_words'])
    if role_hit:
        score += 20
    elif "facebook.com" in domain:
        score += 15 # FB商家页面酌情给过
    else:
        return 0, None # 既没经销商词又不是社媒，可能是普通文章，放弃

    # 4. 提取联系方式与社媒 (对海外客户极度重要)
    emails = list(dict.fromkeys(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
    commercial_email = False
    free_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com']
    for e in emails:
        edomain = e.split('@')[-1].lower()
        if edomain not in free_domains and 'noreply' not in e and 'example' not in e and 'wix' not in e:
            commercial_email = True
            break
    if commercial_email:
        score += 10 # 有企业邮箱加分

    wa_links = list(set(re.findall(r'(https?://(?:wa\.me/|api\.whatsapp\.com/send\?phone=)[0-9]+)', html)))
    fb_links = list(set(re.findall(r'(https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+)', html)))
    fb_links = [l for l in fb_links if not any(x in l for x in ['sharer', 'share', 'plugins', 'events'])]
    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    
    contact_parts = []
    if emails: contact_parts.append("✉️ " + ", ".join(emails[:2]))
    if wa_links: contact_parts.append("💬 WA: " + wa_links[0])
    elif phones: contact_parts.append("📞 " + phones[0])
    
    if fb_links or "facebook.com" in domain:
        score += 5
        fb_str = fb_links[0] if fb_links else url
        contact_parts.append("🌐 FB: " + fb_str)

    if not contact_parts:
        contact_parts.append("官网表单")

    company = soup.title.string.strip() if soup.title else domain

    return score, {
        '公司名称': company[:60] + "..." if len(company)>60 else company,
        '官网/主页': url,
        '匹配产品': ', '.join(matched_kw[:5]),  # 最多展示5个匹配到的产品
        '产品数': len(matched_kw),
        '联系方式': " | ".join(contact_parts),
        '评分': score
    }

def duckduckgo_search(query, region, max_results=5):
    try:
        ddgs = DDGS()
        return [r['href'] for r in ddgs.text(query, region=region, max_results=max_results)]
    except Exception as e:
        return []

# ==================== 会话状态初始化 ====================
if 'excluded_domains' not in st.session_state: st.session_state.excluded_domains = set()
if 'all_leads' not in st.session_state: st.session_state.all_leads = []
if 'current_page' not in st.session_state: st.session_state.current_page = 0
if 'last_search_count' not in st.session_state: st.session_state.last_search_count = 0

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("🌍 搜索配置")
    selected_country = st.selectbox("选择目标语言区 (国家组)", list(COUNTRY_CONFIG.keys()))
    config = COUNTRY_CONFIG[selected_country]
    cities = st.multiselect("可添加城市(可选)", config['cities'], default=config['cities'][:2])

    st.subheader("📦 选择我们的产品线")
    st.caption("勾选越多，越容易找到全品类经销商")
    selected_lines = []
    for line_name in config['product_lines'].keys():
        if st.checkbox(line_name, value=True):
            selected_lines.append(line_name)

    st.subheader("🔧 补充产品关键词")
    manual_keywords = st.text_area("输入其它特定产品词（如 Digitzone 等）每行一个", height=80)

    final_keywords = []
    for line in selected_lines:
        final_keywords.extend(config['product_lines'][line]['search'])
    if manual_keywords.strip():
        manual_list = [k.strip() for k in manual_keywords.splitlines() if k.strip()]
        final_keywords = list(set(final_keywords + manual_list))
    else:
        final_keywords = list(set(final_keywords))

    if final_keywords:
        st.caption(f"当前监控产品词数: {len(final_keywords)}")

    st.markdown("---")
    st.caption(f"已排查域名: {len(st.session_state.excluded_domains)} 个")
    if st.button("清空所有记录", key="clear_all"):
        st.session_state.excluded_domains.clear()
        st.session_state.all_leads.clear()
        st.session_state.current_page = 0
        st.session_state.last_search_count = 0
        st.rerun()

# ==================== 搜索逻辑 ====================
def search_leads(keywords, config, excluded_domains, max_new=5):
    scored_leads = []
    seen = excluded_domains.copy()
    region = config.get("region", "us-en")
    
    queries = []
    for kw in keywords:
        role = random.choice(config['role_words'])
        # 25% 的概率专项搜索 Facebook 的汽修工具经销商
        if random.random() < 0.25:
            queries.append(f'"{kw}" {role} site:facebook.com')
        else:
            queries.append(f'"{kw}" {role}')
    random.shuffle(queries)

    for q in queries:
        if len(scored_leads) >= max_new * 2: break
        urls = duckduckgo_search(q, region=region, max_results=5)
        for url in urls:
            domain = urlparse(url).netloc
            if domain in seen and "facebook.com" not in domain:
                continue
            html = fetch_page(url)
            if not html: continue
            
            score, info = score_lead(html, url, config, keywords)
            if score > 0:
                if not any(url == lead[1]['官网/主页'] for lead in scored_leads):
                    scored_leads.append((score, info))
                    seen.add(domain)
            else:
                seen.add(domain)
        time.sleep(1)

    scored_leads.sort(key=lambda x: x[0], reverse=True)
    return [info for _, info in scored_leads[:max_new]]

if st.button("🔍 智能检索 5 家匹配经销商", type="primary"):
    if not final_keywords:
        st.error("请至少选择一条产品线或输入关键词")
    else:
        with st.spinner("正在全球全网扫街中 (寻找同时售卖1-3件我们产品的潜客)..."):
            leads = search_leads(final_keywords, config, st.session_state.excluded_domains, max_new=5)
        if leads:
            st.session_state.all_leads.extend(leads)
            for l in leads:
                st.session_state.excluded_domains.add(urlparse(l['官网/主页']).netloc)
            st.session_state.last_search_count += 1
            st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
            st.success(f"第 {st.session_state.last_search_count} 次搜索，新增 {len(leads)} 家精准客户")
        else:
            st.warning("暂未发现有效客户，请稍后再试。")

# ==================== 分页显示结果 ====================
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
        st.write(f"页码 {current_page+1}/{total_pages} · 共 {total_leads} 条记录")
    with col4:
        st.download_button(
            "📥 导出 CSV",
            pd.DataFrame(st.session_state.all_leads)[['公司名称','官网/主页','匹配产品','产品数','联系方式','评分']].to_csv(index=False).encode('utf-8-sig'),
            "JYTOOL_B2B_Leads.csv"
        )

    start_idx = current_page * 5
    end_idx = min(start_idx + 5, total_leads)
    for i in range(start_idx, end_idx):
        lead = st.session_state.all_leads[i]
        # 如果产品匹配数 >= 3，给与🔥标识，说明是高度匹配的综合经销商
        score_color = "🔥" if lead['产品数'] >= 3 else ("🟢" if lead['产品数'] == 2 else "🟡")
        
        st.subheader(f"{i+1}. {score_color} {lead['公司名称']} (评分: {lead['评分']})")
        st.markdown(f"🌐 官网/主页: [{lead['官网/主页']}]({lead['官网/主页']})")
        st.markdown(f"🎯 **匹配到我们的产品 ({lead['产品数']}款)**: `{lead['匹配产品']}`")
        st.markdown(f"📞 联系方式: {lead['联系方式']}")
        st.markdown("---")
else:
    st.info("点击上方按钮开始搜索。系统会自动帮您寻找涵盖您 PDF 目录中 1~3 款产品的设备经销商。")
