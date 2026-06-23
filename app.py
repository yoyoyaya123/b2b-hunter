import streamlit as st
import requests
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ddgs import DDGS

st.set_page_config(page_title="B2B全球精准获客-汽保工具", layout="wide")
st.title("🔧 汽车维修专用工具 · 全球B2B精准客户搜索（精准版）")

# ==================== 全球9国产品线配置 ====================
COUNTRY_CONFIG = {
    "德国": {
        "lang": "de", "country": "de", "region": "de-de",
        "cities": ["Berlin", "Hamburg", "München", "Frankfurt", "Stuttgart", "Köln", "Düsseldorf"],
        "role_words": ["Großhandel", "Großhändler", "Importeur", "Import", "Distributor", "Händler", "Lieferant", "Fachhandel"],
        "exclude_words": ["Werkstatt", "Reparatur", "Service-Center", "Autohaus", "Reifenservice", "Karosseriebau", "Lackiererei", "Tuning"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["Kühlsystem-Dichtheitsprüfer", "Klimaservice-Werkzeug", "Klimaanlagen-Reparaturwerkzeug", "Kältemittel-Füllschlauch", "Klima-Lecksuchgerät"],
                "evidence": ["Kühlsystem-Dichtheitsprüfer", "Klimaservice-Werkzeug", "Klimaanlagen-Reparaturwerkzeug", "Kältemittel", "Klima-Lecksuchgerät", "Klimaservice-Station"]
            },
            "仪表检测工具": {
                "search": ["Zylinderdruckprüfer", "Kraftstoffdruckmessgerät", "Dieseleinspritzung-Tester", "Motor-Diagnosegerät", "Unterdruckmanometer", "Abgasgegendruckprüfer"],
                "evidence": ["Zylinderdruckprüfer", "Kraftstoffdruckmessgerät", "Dieseleinspritzung-Tester", "Motor-Diagnosegerät", "Kompressionstester", "Einspritzdüsen-Tester"]
            },
            "刹车/底盘/结构": {
                "search": ["Bremskolbenrückstellsatz", "Fahrwerk-Reparaturwerkzeug", "Kugelgelenkabzieher", "Kupplungszentrierwerkzeug", "Radlager-Abzieher-Set", "Stoßdämpfer-Montagewerkzeug"],
                "evidence": ["Bremskolbenrückstellsatz", "Fahrwerk-Reparaturwerkzeug", "Kugelgelenkabzieher", "Kupplungszentrierwerkzeug", "Radlager-Abzieher", "Stoßdämpfer-Montagewerkzeug"]
            },
            "液体更换/系统维护": {
                "search": ["Bremsenentlüftungsgerät", "Kühlmittel-Befüllset", "Bremsflüssigkeitswechsler", "Kältemittelöl-Einfüllwerkzeug", "Absaug- und Einfüllspritze"],
                "evidence": ["Bremsenentlüftungsgerät", "Kühlmittel-Befüllset", "Bremsflüssigkeitswechsler", "Kältemittelöl-Einfüllwerkzeug", "Absaugspritze", "Entlüftungsgerät"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set", "Innenraum-Demontagewerkzeug", "Öldichtungs-Haken-Set", "Schlauchklemmen-Zangen-Set"],
                "evidence": ["Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set", "Innenraum-Demontagewerkzeug", "Öldichtungs-Haken-Set", "Schlauchklemmen-Zangen-Set", "Verkleidungs-Clip"]
            }
        }
    },
    "法国": {
        "lang": "fr", "country": "fr", "region": "fr-fr",
        "cities": ["Paris", "Lyon", "Marseille", "Lille", "Bordeaux", "Toulouse", "Nantes"],
        "role_words": ["grossiste", "importateur", "distributeur", "fournisseur", "revendeur"],
        "exclude_words": ["garage", "atelier de réparation", "carrosserie", "peinture", "pneumatique"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["détecteur de fuite de radiateur", "outil de climatisation auto", "manifold frigorifique", "kit de charge de réfrigérant", "détecteur de fuite de clim"],
                "evidence": ["détecteur de fuite de radiateur", "outil de climatisation", "manifold frigorifique", "kit de charge", "détecteur de fuite de clim"]
            },
            "仪表检测工具": {
                "search": ["testeur de compression", "manomètre de pression d'essence", "testeur d'injecteur diesel", "outil de diagnostic moteur", "dépressiomètre", "testeur de contre-pression"],
                "evidence": ["testeur de compression", "manomètre de pression d'essence", "testeur d'injecteur diesel", "diagnostic moteur", "dépressiomètre"]
            },
            "刹车/底盘/结构": {
                "search": ["kit de repose-culasse", "outil de réparation de suspension", "extracteur de rotule", "outil de centrage d'embrayage", "extracteur de roulement", "outil de montage d'amortisseur"],
                "evidence": ["repose-culasse", "outil de suspension", "extracteur de rotule", "centrage d'embrayage", "extracteur de roulement"]
            },
            "液体更换/系统维护": {
                "search": ["purgeur de frein", "kit de remplissage de liquide de refroidissement", "échangeur de liquide de frein", "outil de remplissage d'huile de réfrigérant", "seringue d'aspiration et de remplissage"],
                "evidence": ["purgeur de frein", "remplissage de liquide de refroidissement", "échangeur de liquide de frein", "seringue d'aspiration"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["kit de leviers en nylon", "kit de clips auto", "outil de démontage intérieur", "kit de crochets à joint", "kit de pinces pour colliers"],
                "evidence": ["leviers en nylon", "clips auto", "démontage intérieur", "crochets à joint", "pinces pour colliers"]
            }
        }
    },
    "西班牙": {
        "lang": "es", "country": "es", "region": "es-es",
        "cities": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao", "Zaragoza"],
        "role_words": ["mayorista", "importador", "distribuidor", "proveedor", "comercio al por mayor"],
        "exclude_words": ["taller", "reparación", "carrocería", "pintura", "neumáticos"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["probador de fugas de radiador", "herramienta de climatización", "manómetro de refrigerante", "kit de carga de refrigerante", "detector de fugas de aire acondicionado"],
                "evidence": ["probador de fugas de radiador", "herramienta de climatización", "manómetro de refrigerante", "kit de carga", "detector de fugas"]
            },
            "仪表检测工具": {
                "search": ["comprobador de compresión", "manómetro de presión de combustible", "probador de inyectores diésel", "herramienta de diagnóstico del motor", "vacuómetro", "probador de contrapresión"],
                "evidence": ["comprobador de compresión", "manómetro de presión", "probador de inyectores", "diagnóstico del motor"]
            },
            "刹车/底盘/结构": {
                "search": ["juego de retroceso de freno", "herramienta de reparación de suspensión", "extractor de rótulas", "herramienta de centrado de embrague", "extractor de rodamientos", "montador de amortiguadores"],
                "evidence": ["retroceso de freno", "herramienta de suspensión", "extractor de rótulas", "centrado de embrague", "extractor de rodamientos"]
            },
            "液体更换/系统维护": {
                "search": ["purgador de frenos", "kit de llenado de refrigerante", "cambiador de líquido de frenos", "herramienta de llenado de aceite de refrigerante", "jeringa de aspiración y llenado"],
                "evidence": ["purgador de frenos", "llenado de refrigerante", "cambiador de líquido de frenos", "jeringa de aspiración"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["kit de palancas de nailon", "kit de clips de coche", "herramienta de desmontaje interior", "kit de ganchos para retenes", "kit de alicates para abrazaderas"],
                "evidence": ["palancas de nailon", "clips de coche", "desmontaje interior", "ganchos para retenes", "alicates para abrazaderas"]
            }
        }
    },
    "葡萄牙": {
        "lang": "pt", "country": "pt", "region": "pt-pt",
        "cities": ["Lisboa", "Porto", "Braga", "Coimbra", "Faro"],
        "role_words": ["grossista", "importador", "distribuidor", "fornecedor", "revendedor"],
        "exclude_words": ["oficina", "reparação", "carroçaria", "pintura", "pneus"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["detector de fugas de radiador", "ferramenta de ar condicionado", "manifold de refrigerante", "kit de carga de refrigerante", "detector de fugas de AC"],
                "evidence": ["detector de fugas", "ferramenta de ar condicionado", "manifold de refrigerante", "kit de carga"]
            },
            "仪表检测工具": {
                "search": ["testador de compressão", "manómetro de pressão de combustível", "testador de injetores diesel", "ferramenta de diagnóstico do motor", "vacuómetro", "testador de contrapressão"],
                "evidence": ["testador de compressão", "manómetro de pressão", "testador de injetores", "diagnóstico do motor"]
            },
            "刹车/底盘/结构": {
                "search": ["kit de recuo do travão", "ferramenta de reparação de suspensão", "extrator de rótulas", "ferramenta de centragem da embraiagem", "extrator de rolamentos", "montador de amortecedores"],
                "evidence": ["recuo do travão", "ferramenta de suspensão", "extrator de rótulas", "centragem da embraiagem"]
            },
            "液体更换/系统维护": {
                "search": ["purga de travões", "kit de enchimento de líquido de refrigeração", "trocador de fluido de travões", "ferramenta de enchimento de óleo de refrigerante", "seringa de aspiração e enchimento"],
                "evidence": ["purga de travões", "enchimento de líquido", "trocador de fluido", "seringa de aspiração"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["kit de alavancas de nylon", "kit de clips automóvel", "ferramenta de desmontagem interior", "kit de ganchos para retentores", "kit de alicates para braçadeiras"],
                "evidence": ["alavancas de nylon", "clips automóvel", "desmontagem interior", "ganchos para retentores"]
            }
        }
    },
    "意大利": {
        "lang": "it", "country": "it", "region": "it-it",
        "cities": ["Milano", "Roma", "Napoli", "Torino", "Bologna", "Firenze"],
        "role_words": ["grossista", "importatore", "distributore", "fornitore", "rivenditore"],
        "exclude_words": ["officina", "riparazione", "carrozzeria", "verniciatura", "pneumatici"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["tester perdite radiatore", "attrezzo per aria condizionata", "manifold refrigerante", "kit di ricarica refrigerante", "rilevatore perdite AC"],
                "evidence": ["tester perdite", "attrezzo per aria condizionata", "manifold refrigerante", "kit di ricarica"]
            },
            "仪表检测工具": {
                "search": ["tester di compressione", "manometro pressione carburante", "tester iniettori diesel", "strumento di diagnosi motore", "vacuometro", "tester di contropressione"],
                "evidence": ["tester di compressione", "manometro pressione", "tester iniettori", "diagnosi motore"]
            },
            "刹车/底盘/结构": {
                "search": ["kit rientro pistoncini freno", "attrezzo per sospensioni", "estrattore giunti sferici", "centraggio frizione", "estrattore cuscinetti", "montatore ammortizzatori"],
                "evidence": ["rientro pistoncini", "attrezzo per sospensioni", "estrattore giunti", "centraggio frizione"]
            },
            "液体更换/系统维护": {
                "search": ["spurgo freni", "kit di riempimento liquido raffreddamento", "cambiatore liquido freni", "attrezzo riempimento olio refrigerante", "siringa aspirazione e riempimento"],
                "evidence": ["spurgo freni", "riempimento liquido", "cambiatore liquido", "siringa aspirazione"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["set leve in nylon", "set clip auto", "attrezzo smontaggio interni", "set ganci per guarnizioni", "set pinze per fascette"],
                "evidence": ["leve in nylon", "clip auto", "smontaggio interni", "ganci per guarnizioni"]
            }
        }
    },
    "英国": {
        "lang": "en", "country": "uk", "region": "uk-en",
        "cities": ["London", "Birmingham", "Manchester", "Glasgow", "Liverpool", "Bristol"],
        "role_words": ["wholesaler", "importer", "distributor", "supplier"],
        "exclude_words": ["garage", "repair", "body shop", "paint", "tyre", "auto service", "dealership"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit", "AC leak detector"],
                "evidence": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit"]
            },
            "仪表检测工具": {
                "search": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic tool", "vacuum gauge", "exhaust back pressure tester"],
                "evidence": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic"]
            },
            "刹车/底盘/结构": {
                "search": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment tool", "bearing puller", "shock absorber mounting tool"],
                "evidence": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment"]
            },
            "液体更换/系统维护": {
                "search": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "refrigerant oil fill tool", "suction and fill syringe"],
                "evidence": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "suction syringe"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["nylon pry bar set", "car clip set", "interior trim removal tool", "oil seal hook set", "hose clamp pliers set"],
                "evidence": ["nylon pry bar set", "car clip set", "interior trim removal", "oil seal hook", "hose clamp pliers"]
            }
        }
    },
    "美国": {
        "lang": "en", "country": "us", "region": "us-en",
        "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Miami", "Dallas"],
        "role_words": ["wholesaler", "importer", "distributor", "supplier"],
        "exclude_words": ["garage", "repair shop", "body shop", "paint shop", "tire shop", "auto service", "quick lube", "car wash", "dealership"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit", "AC leak detector"],
                "evidence": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit"]
            },
            "仪表检测工具": {
                "search": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic tool", "vacuum gauge", "exhaust back pressure tester"],
                "evidence": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic"]
            },
            "刹车/底盘/结构": {
                "search": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment tool", "bearing puller", "shock absorber mounting tool"],
                "evidence": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment"]
            },
            "液体更换/系统维护": {
                "search": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "refrigerant oil fill tool", "suction and fill syringe"],
                "evidence": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "suction syringe"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["nylon pry bar set", "car clip set", "interior trim removal tool", "oil seal hook set", "hose clamp pliers set"],
                "evidence": ["nylon pry bar set", "car clip set", "interior trim removal", "oil seal hook", "hose clamp pliers"]
            }
        }
    },
    "委内瑞拉": {
        "lang": "es", "country": "ve", "region": "ve-es",
        "cities": ["Caracas", "Maracaibo", "Valencia", "Barquisimeto", "Maracay"],
        "role_words": ["mayorista", "importador", "distribuidor", "proveedor", "comercio al por mayor"],
        "exclude_words": ["taller", "reparación", "carrocería", "pintura", "neumáticos", "lubricentro", "autolavado"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["probador de fugas de radiador", "herramienta de climatización", "manómetro de refrigerante", "kit de carga de refrigerante", "detector de fugas de aire acondicionado"],
                "evidence": ["probador de fugas de radiador", "herramienta de climatización", "manómetro de refrigerante", "kit de carga", "detector de fugas"]
            },
            "仪表检测工具": {
                "search": ["comprobador de compresión", "manómetro de presión de combustible", "probador de inyectores diésel", "herramienta de diagnóstico del motor", "vacuómetro", "probador de contrapresión"],
                "evidence": ["comprobador de compresión", "manómetro de presión", "probador de inyectores", "diagnóstico del motor"]
            },
            "刹车/底盘/结构": {
                "search": ["juego de retroceso de freno", "herramienta de reparación de suspensión", "extractor de rótulas", "herramienta de centrado de embrague", "extractor de rodamientos", "montador de amortiguadores"],
                "evidence": ["retroceso de freno", "herramienta de suspensión", "extractor de rótulas", "centrado de embrague", "extractor de rodamientos"]
            },
            "液体更换/系统维护": {
                "search": ["purgador de frenos", "kit de llenado de refrigerante", "cambiador de líquido de frenos", "herramienta de llenado de aceite de refrigerante", "jeringa de aspiración y llenado"],
                "evidence": ["purgador de frenos", "llenado de refrigerante", "cambiador de líquido de frenos", "jeringa de aspiración"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["kit de palancas de nailon", "kit de clips de coche", "herramienta de desmontaje interior", "kit de ganchos para retenes", "kit de alicates para abrazaderas"],
                "evidence": ["palancas de nailon", "clips de coche", "desmontaje interior", "ganchos para retenes", "alicates para abrazaderas"]
            }
        }
    },
    "斯里兰卡": {
        "lang": "en", "country": "lk", "region": "lk-en",
        "cities": ["Colombo", "Kandy", "Galle", "Jaffna", "Negombo"],
        "role_words": ["wholesaler", "importer", "distributor", "supplier", "dealer"],
        "exclude_words": ["garage", "repair", "service station", "paint shop", "tyre shop", "auto service", "workshop"],
        "product_lines": {
            "空调/冷却系统": {
                "search": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit", "AC leak detector"],
                "evidence": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit"]
            },
            "仪表检测工具": {
                "search": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic tool", "vacuum gauge", "exhaust back pressure tester"],
                "evidence": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic"]
            },
            "刹车/底盘/结构": {
                "search": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment tool", "bearing puller", "shock absorber mounting tool"],
                "evidence": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment"]
            },
            "液体更换/系统维护": {
                "search": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "refrigerant oil fill tool", "suction and fill syringe"],
                "evidence": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "suction syringe"]
            },
            "内饰撬棒/卡扣耗材": {
                "search": ["nylon pry bar set", "car clip set", "interior trim removal tool", "oil seal hook set", "hose clamp pliers set"],
                "evidence": ["nylon pry bar set", "car clip set", "interior trim removal", "oil seal hook", "hose clamp pliers"]
            }
        }
    }
}

# ==================== 辅助函数 ====================
def fetch_page(url, retries=2):
    for attempt in range(retries):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(url, timeout=15, headers=headers)
            resp.raise_for_status()
            return resp.text
        except:
            time.sleep(2)
    return None

def score_lead(html, url, config, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    
    # 排除词检查
    for word in config['exclude_words']:
        if word.lower() in text:
            return 0, None

    # 产品关键词必须命中
    matched_kw = [kw for kw in keywords if kw.lower() in text]
    if not matched_kw:
        return 0, None
    
    score = 10  # 基础分：包含产品词

    # 角色词必须出现
    role_hit = any(role.lower() in text for role in config['role_words'])
    if not role_hit:
        return 0, None  # 强制要求
    score += 20

    # 联系方式质量
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    commercial_email = False
    free_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com']
    for e in emails:
        domain = e.split('@')[1].lower()
        if domain not in free_domains and 'noreply' not in e and 'example' not in e:
            commercial_email = True
            break
    if commercial_email:
        score += 10

    domain = urlparse(url).netloc
    company = soup.title.string.strip() if soup.title else domain
    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    contact = "邮箱: " + (", ".join(emails[:2]) if emails else "无") + "; 电话: " + (phones[0] if phones else "官网表单")

    return score, {
        '公司名称': company,
        '官网': url,
        '匹配产品': ', '.join(matched_kw[:3]),
        '联系方式': contact,
        '评分': score
    }

def duckduckgo_search(query, region, max_results=5):
    try:
        with DDGS() as ddgs:
            return [r['href'] for r in ddgs.text(query, region=region, max_results=max_results)]
    except Exception as e:
        st.warning(f"搜索出错: {e}")
        return []

# ==================== 会话状态初始化 ====================
if 'excluded_domains' not in st.session_state:
    st.session_state.excluded_domains = set()
if 'all_leads' not in st.session_state:
    st.session_state.all_leads = []      # 保存所有搜索到的线索
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0    # 当前页码（0-based）
if 'last_search_count' not in st.session_state:
    st.session_state.last_search_count = 0   # 搜索次数统计

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("🌍 搜索配置")
    selected_country = st.selectbox("选择目标国家", list(COUNTRY_CONFIG.keys()))
    config = COUNTRY_CONFIG[selected_country]
    cities = st.multiselect("选择城市", config['cities'], default=config['cities'][:3])

    st.subheader("📦 选择产品线")
    selected_lines = []
    for line_name in config['product_lines'].keys():
        if st.checkbox(line_name, value=True):
            selected_lines.append(line_name)

    st.subheader("🔧 手动关键词")
    manual_keywords = st.text_area("每行一个关键词（可选）", height=80)

    final_keywords = []
    for line in selected_lines:
        final_keywords.extend(config['product_lines'][line]['search'])
    if manual_keywords.strip():
        manual_list = [k.strip() for k in manual_keywords.splitlines() if k.strip()]
        final_keywords = list(set(final_keywords + manual_list))
    else:
        final_keywords = list(set(final_keywords))

    if final_keywords:
        st.text(f"搜索词数: {len(final_keywords)}")
        with st.expander("查看搜索词"):
            st.write(final_keywords)

    st.markdown("---")
    st.caption(f"已排除域名: {len(st.session_state.excluded_domains)} 个")
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
        queries.append(f'"{kw}" {role}')
    random.shuffle(queries)

    for q in queries:
        if len(scored_leads) >= max_new * 2:
            break
        urls = duckduckgo_search(q, region=region, max_results=5)
        for url in urls:
            domain = urlparse(url).netloc
            if domain in seen:
                continue
            html = fetch_page(url)
            if not html:
                continue
            score, info = score_lead(html, url, config, keywords)
            if score > 0:
                scored_leads.append((score, info))
                seen.add(domain)
            else:
                seen.add(domain)
        time.sleep(1)

    # 按评分排序，取前 max_new 个
    scored_leads.sort(key=lambda x: x[0], reverse=True)
    final_leads = [info for _, info in scored_leads[:max_new]]
    return final_leads

if st.button("🔍 搜索5家精准客户", type="primary"):
    if not final_keywords:
        st.error("请至少选择一条产品线或输入关键词")
    elif not cities:
        st.error("请至少选择一个城市")
    else:
        with st.spinner("正在搜索并评估客户质量..."):
            leads = search_leads(final_keywords, config, st.session_state.excluded_domains, max_new=5)
        if leads:
            # 将新线索追加到总列表
            st.session_state.all_leads.extend(leads)
            # 排除域名
            for l in leads:
                st.session_state.excluded_domains.add(urlparse(l['官网']).netloc)
            st.session_state.last_search_count += 1
            # 自动跳转到最后一页
            st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
            st.success(f"第 {st.session_state.last_search_count} 次搜索，新增 {len(leads)} 家客户（总记录 {len(st.session_state.all_leads)} 条）")
        else:
            st.warning("未找到同时包含产品词和批发/进口商词汇的网站。")

# ==================== 分页显示结果 ====================
if st.session_state.all_leads:
    total_leads = len(st.session_state.all_leads)
    total_pages = (total_leads - 1) // 5 + 1
    current_page = st.session_state.current_page

    # 导航栏
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
            "📥 导出全部记录 CSV",
            pd.DataFrame(st.session_state.all_leads)[['公司名称','官网','匹配产品','联系方式','评分']].to_csv(index=False).encode('utf-8-sig'),
            "all_leads.csv"
        )

    # 当前页的5条记录
    start_idx = current_page * 5
    end_idx = min(start_idx + 5, total_leads)
    for i in range(start_idx, end_idx):
        lead = st.session_state.all_leads[i]
        score_color = "🟢" if lead['评分'] >= 30 else "🟡"
        st.subheader(f"{i+1}. {score_color} {lead['公司名称']} (评分: {lead['评分']})")
        st.markdown(f"🌐 官网: [{lead['官网']}]({lead['官网']})")
        st.markdown(f"🔧 匹配产品: {lead['匹配产品']}")
        st.markdown(f"📞 联系方式: {lead['联系方式']}")
        st.markdown("---")
else:
    st.info("点击上方按钮开始搜索，每次搜索新增5家精准客户")
