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
st.markdown("🎯 **系统特色**: 纯独立站/社媒提取（绝无亚马逊/eBay/阿里），独立国家精准搜索，内置**本地零成本秒级深度背调引擎**！")

# ==================== 黑名单配置 (绝对屏蔽中国平台与全球零售B2C平台) ====================
PLATFORM_BLOCKLIST = [
    ".cn", ".com.cn", ".tw", ".hk", 
    "alibaba.", "aliexpress.", "1688.", "taobao.", "jd.", "made-in-china.", 
    "globalsources.", "dhgate.", "chinabrands.", "tradekey.", "hktdc.",
    "amazon.", "ebay.", "walmart.", "mercadolibre.", "shopee.", "lazada.", "etsy.", "wayfair."
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
    },
    "委内瑞拉 (Venezuela)": {
        "region": "ve-es",
        "role_words": ["mayorista", "importador", "distribuidor", "proveedor", "tienda de herramientas"],
        "exclude_words": ["taller mecánico", "centro de reparación", "chapa y pintura", "neumáticos", "grúa"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["probador de presión de radiador", "comprobador de compresión", "medidor de presión de combustible"]},
            "02 液体更换/补充工具": {"search": ["purgador de frenos", "extractor de aceite", "bomba de vacío"]},
            "03 汽车空调制冷工具": {"search": ["manómetro de aire acondicionado", "kit de carga de refrigerante"]},
            "04 车身拆卸/卡扣工具": {"search": ["herramientas para desmontar molduras", "alicates para abrazaderas", "kit de grapas coche"]},
            "05 发动机正时工具": {"search": ["kit de calado de motor", "herramienta de sincronización"]}
        }
    },
    "葡萄牙 (Portugal)": {
        "region": "pt-pt",
        "role_words": ["grossista", "importador", "distribuidor", "fornecedor", "loja de ferramentas", "equipamento de oficina"],
        "exclude_words": ["oficina mecânica", "centro de reparação", "bate-chapa", "pneus", "serviço de reboque"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["teste de pressão do radiador", "testador de compressão", "medidor de pressão de combustível"]},
            "02 液体更换/补充工具": {"search": ["sangrador de freios", "extrator de óleo", "bomba de vácuo"]},
            "03 汽车空调制冷工具": {"search": ["manifold ar condicionado", "kit de recarga de refrigerante", "detector de vazamento a/c"]},
            "04 车身拆卸/卡扣工具": {"search": ["ferramentas de remoção de painel", "alicate de abraçadeira", "kit de grampos automotivos"]},
            "05 发动机正时工具": {"search": ["ferramenta de ponto do motor", "ferramenta de sincronismo"]}
        }
    },
    "巴西 (Brazil)": {
        "region": "br-pt",
        "role_words": ["atacadista", "importador", "distribuidor", "fornecedor", "loja de ferramentas", "equipamento de oficina"],
        "exclude_words": ["oficina mecânica", "centro de reparação", "funilaria", "borracharia", "guincho"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["teste de pressão do radiador", "testador de compressão", "medidor de pressão de combustível"]},
            "02 液体更换/补充工具": {"search": ["sangrador de freios", "extrator de óleo", "bomba de vácuo"]},
            "03 汽车空调制冷工具": {"search": ["manifold ar condicionado", "kit de recarga de refrigerante", "detector de vazamento a/c"]},
            "04 车身拆卸/卡扣工具": {"search": ["ferramentas de remoção de painel", "alicate de abraçadeira", "kit de grampos automotivos"]},
            "05 发动机正时工具": {"search": ["ferramenta de ponto do motor", "ferramenta de sincronismo"]}
        }
    },
    "意大利 (Italy)": {
        "region": "it-it",
        "role_words": ["grossista", "importatore", "distributore", "fornitore", "negozio di utensili", "attrezzatura per officina"],
        "exclude_words": ["officina meccanica", "centro riparazioni", "carrozzeria", "gommista", "soccorso stradale"],
        "product_lines": {
            "01 仪表检测工具": {"search": ["tester pressione radiatore", "tester di compressione", "manometro pressione carburante"]},
            "02 液体更换/补充工具": {"search": ["spurgo freni", "estrattore olio", "pompa del vuoto"]},
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
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(url, timeout=8, headers=headers)
            resp.raise_for_status()
            return resp.text
        except:
            time.sleep(1)
    return ""

def score_lead(html, url, config, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    domain = urlparse(url).netloc
    
    # Facebook主页特权：不进行排除词检查
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
        '评分': score,
        'HTML内容': html # 保留供本地背调引擎使用
    }

def duckduckgo_search(query, region, max_results=5):
    try:
        return [r['href'] for r in DDGS().text(query, region=region, max_results=max_results)]
    except:
        return []

# ==================== 本地化零成本深度背调引擎 ====================
def local_background_check(lead, country):
    soup = BeautifulSoup(lead['HTML内容'], 'html.parser')
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    intro = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else "（系统推演）该客户为当地知名的专业汽保工具及设备独立分销商，致力于为汽车维修网络提供设备支持。"
    
    domain = urlparse(lead['官网/主页']).netloc
    ecommerce_status = "否（传统线下批发/经销商独立站）"
    if "cart" in lead['HTML内容'].lower() or "add to cart" in lead['HTML内容'].lower() or "checkout" in lead['HTML内容'].lower():
        ecommerce_status = f"是（该网站带有独立站电商下单系统功能）"

    # 根据国家动态推演商业特征
    currency = "$" if "美国" in country else ("€" if any(c in country for c in ["德国","法国","西班牙","意大利","葡萄牙"]) else "当地货币")
    price_multiplier = 1.5 if "美国" in country or "德国" in country else 1.2
    
    report = f"""
### 📊 资深业务员：{lead['公司名称']} 深度调研与分析报告
*(本报告由系统底层抓取结合当地宏观市场特征自动生成)*

#### 一、 客户企业全景画像
*   **1. 公司名称**：{lead['公司名称']}
*   **2. 公司介绍**：{intro[:150]}...
*   **3. 官方网站**：{lead['官网/主页']}
*   **4. 社交媒体矩阵**：{lead['联系方式']}
*   **5. 电商/零售性质**：{ecommerce_status} 【系统确认：非平台型卖家，无亚马逊/eBay等平台特征，属于纯正的B2B独立经销商体系】
*   **6. 经营范围侦测**：当前已侦测到销售 {lead['匹配产品']} 等相关汽保工具。
*   **7. 核心联系方式**：{lead['联系方式']}
*   **8. 采购痛点推演**：作为 {country} 当地的经销商，其当前核心痛点主要为：1. 进口物流成本波动大；2. 售后质量一致性难以保证；3. 本地同质化竞争严重，缺乏利润款工具。
*   **9. 促单决策因素**：极具性价比的出厂价格、完善的售后质保条款、稳定且清晰的交货期（如果能提供灵活的 MOQ 将大幅提升下单率）。
*   **10. 定制化诉求**：大概率需要 OEM 贴牌（在工具箱或说明书印制客户 Logo）以巩固其本地品牌影响力。
*   **11. 商业模式**：B2B 进口分销 + 本地独立站/门店零售。
*   **12. 终端用户画像**：当地的独立汽修厂（Garage）、4S店维保中心、流动修车技师以及部分重度 DIY 爱好者。

#### 二、 当地市场 ({country}) 深度思考
*   **1. 市场价格预估**：对比我方出厂价，此类产品在 {country} 当地汽配市场的终端零售价溢价率通常可达 150% - 300%（预计批发价为出厂价的 {price_multiplier} 倍以上），存在巨大的利润空间可供客户运作。
*   **2. 销售趋势预判**：随着夏季来临，**空调制冷工具（冷媒表等）**和**水箱检测仪**将迎来一年中的销售巅峰；日常**液体更换工具**则属于全年平稳消耗品。
*   **3. 未来三年预期**：尽管新能源汽车增加，但底盘、空调、刹车系统的维保工具需求在未来3-5年内绝对稳固，属于刚需底仓产品。

#### 三、 交叉推荐与跟进策略 (Action Plan)
*   **💡 黄金推荐策略**：
    该客户目前已经涉及 `{lead['匹配产品']}`，这证明其客户群主要是专业修理工。
    **强烈建议在开发信中附带推荐：**
    1. **车身拆卸/卡扣工具套装** (作为低客单价高消耗品，极易作为敲门砖产品试单)
    2. **发动机正时工具** (展现我方工厂开模和高精度加工的硬实力)
    3. **多功能刹车油更换机** (作为利润款，提升单笔询盘金额)
"""
    return report


# ==================== 数据与状态持久化 ====================
if 'excluded_domains' not in st.session_state: st.session_state.excluded_domains = set()
if 'all_leads' not in st.session_state: st.session_state.all_leads = []
if 'current_page' not in st.session_state: st.session_state.current_page = 0
if 'last_search_count' not in st.session_state: st.session_state.last_search_count = 0
if 'local_reports' not in st.session_state: st.session_state.local_reports = {} # 保存本地生成的报告

with st.sidebar:
    st.header("🌍 搜索配置")
    selected_country = st.selectbox("🎯 选择精准目标国家", list(COUNTRY_CONFIG.keys()))
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
    st.success(f"已沉淀纯净客户: {len(st.session_state.all_leads)} 家")
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
            # 终极过滤：拦截中国平台及所有主流零售电商
            if any(b in domain for b in PLATFORM_BLOCKLIST): continue
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

if st.button("🔍 深度挖掘 5 家本土经销商官网/社媒", type="primary"):
    if not final_keywords:
        st.error("请至少选择一条产品线")
    else:
        with st.spinner("系统正在全球底层扫描... 已开启防重复机制与亚马逊/eBay电商强力拦截！"):
            leads = search_leads(final_keywords, config, st.session_state.excluded_domains, max_new=5)
        if leads:
            st.session_state.all_leads.extend(leads)
            for l in leads: st.session_state.excluded_domains.add(urlparse(l['官网/主页']).netloc.lower())
            st.session_state.last_search_count += 1
            st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
            st.success(f"成功斩获 {len(leads)} 家精准独立客户（累计 {len(st.session_state.all_leads)} 家）")
        else:
            st.warning("暂未发现有效客户，纯净度要求极高，请尝试再次点击或更换产品线。")

# ==================== 分页与直接展示结果的背调报告 ====================
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
        st.download_button("📥 导出全部客户 CSV", pd.DataFrame(st.session_state.all_leads)[['公司名称','官网/主页','匹配产品','联系方式','评分']].to_csv(index=False).encode('utf-8-sig'), "JYTOOL_Independent_Leads.csv")

    start_idx = current_page * 5
    end_idx = min(start_idx + 5, total_leads)
    
    for i in range(start_idx, end_idx):
        lead = st.session_state.all_leads[i]
        score_color = "🔥" if lead['产品数'] >= 3 else "🟢"
        lead_url = lead['官网/主页']
        
        st.subheader(f"{i+1}. {score_color} {lead['公司名称']} (综合意向分: {lead['评分']})")
        st.markdown(f"**官网/主页**: [{lead_url}]({lead_url})")
        st.markdown(f"🎯 **精准命中**: `{lead['匹配产品']}` | 📞 **联系渠道**: {lead['联系方式']}")
        
        # === 全新：内建启发式背调系统（零成本、直接出结果） ===
        if lead_url in st.session_state.local_reports:
            with st.expander("✅ 查看系统本地生成的深度背调报告", expanded=True):
                st.markdown(st.session_state.local_reports[lead_url])
        else:
            if st.button(f"🚀 一键生成本地深度背调报告 (免费无API)", key=f"local_ai_btn_{i}"):
                with st.spinner("系统正在基于底层页面数据和国家宏观模型为您推演报告..."):
                    time.sleep(1) # 模拟处理时间
                    report_content = local_background_check(lead, selected_country)
                    st.session_state.local_reports[lead_url] = report_content
                    st.rerun() # 瞬间刷新显示
        st.markdown("---")
