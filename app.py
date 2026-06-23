import streamlit as st
import requests
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ddgs import DDGS  # 使用新包名
from PIL import Image
import torch
import clip
import io
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

st.set_page_config(page_title="B2B全球精准获客-汽保工具", layout="wide")
st.title("🔧 汽车维修专用工具 · 全球B2B精准客户搜索（图片+关键词）")

# ==================== 加载 CLIP 模型 ====================
@st.cache_resource
def load_clip_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    return model, preprocess, device

model, preprocess, device = load_clip_model()

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
def get_image_features(image: Image.Image):
    image_input = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        features = model.encode_image(image_input)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().flatten()

def classify_image(image: Image.Image, product_line_names):
    text_tokens = clip.tokenize(product_line_names).to(device)
    image_input = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        logits_per_image, _ = model(image_input, text_tokens)
        probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]
    best_idx = probs.argmax()
    return product_line_names[best_idx], probs[best_idx]

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

def extract_info(html, url, exclude_words, keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text().lower()
    for word in exclude_words:
        if word.lower() in text:
            return None
    if not any(kw.lower() in text for kw in keywords):
        return None

    domain = urlparse(url).netloc
    company = soup.title.string.strip() if soup.title else domain

    emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
    emails = [e for e in emails if 'noreply' not in e and 'example' not in e]

    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    contact = "邮箱: " + (", ".join(emails) if emails else "无") + "; 电话: " + (phones[0] if phones else "官网表单")

    return {
        '公司名称': company,
        '官网': url,
        '匹配产品': '',
        '联系方式': contact,
        'html': html,
    }

def get_website_images(html, base_url, max_images=3):
    soup = BeautifulSoup(html, 'html.parser')
    img_tags = soup.find_all('img', src=True)
    img_urls = []
    for img in img_tags:
        src = img['src']
        if not src.startswith('http'):
            src = requests.compat.urljoin(base_url, src)
        if src not in img_urls:
            img_urls.append(src)
        if len(img_urls) >= max_images:
            break
    return img_urls

def download_image(img_url, timeout=8):
    try:
        resp = requests.get(img_url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except:
        pass
    return None

def compute_similarity(user_features, website_images):
    if not website_images:
        return 0.0, None
    sims, valid_imgs = [], []
    for img_url in website_images:
        pil_img = download_image(img_url)
        if pil_img:
            feat = get_image_features(pil_img)
            sim = cosine_similarity([user_features], [feat])[0][0]
            sims.append(sim)
            valid_imgs.append(pil_img)
    if not sims:
        return 0.0, None
    max_idx = np.argmax(sims)
    return sims[max_idx], valid_imgs[max_idx]

def duckduckgo_search(query, region, max_results=5):
    try:
        with DDGS() as ddgs:
            return [r['href'] for r in ddgs.text(query, region=region, max_results=max_results)]
    except Exception as e:
        st.warning(f"搜索出错: {e}")
        return []

# ==================== 会话状态 ====================
if 'excluded_domains' not in st.session_state:
    st.session_state.excluded_domains = set()
if 'uploaded_images' not in st.session_state:
    st.session_state.uploaded_images = []
if 'user_image_features' not in st.session_state:
    st.session_state.user_image_features = None
if 'search_count' not in st.session_state:
    st.session_state.search_count = 0

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("🌍 搜索配置")
    selected_country = st.selectbox("选择目标国家", list(COUNTRY_CONFIG.keys()))
    config = COUNTRY_CONFIG[selected_country]

    cities = st.multiselect("选择城市", config['cities'], default=config['cities'][:3])

    st.subheader("📷 上传产品图片")
    uploaded_files = st.file_uploader("选择1-5张产品照片", type=["png", "jpg", "jpeg"],
                                      accept_multiple_files=True, key="image_uploader")

    if uploaded_files:
        st.session_state.uploaded_images = [Image.open(f).convert("RGB") for f in uploaded_files]
        features_list = [get_image_features(img) for img in st.session_state.uploaded_images]
        st.session_state.user_image_features = np.mean(features_list, axis=0)
        cols = st.columns(len(uploaded_files))
        for idx, img in enumerate(st.session_state.uploaded_images):
            cols[idx].image(img, width=80, caption=f"图{idx+1}")
    else:
        st.session_state.uploaded_images = []
        st.session_state.user_image_features = None

    st.subheader("🔧 关键词设置")
    manual_keywords = st.text_area("手动补充关键词（每行一个）", height=80)

    auto_keywords = []
    if st.session_state.uploaded_images:
        product_line_names = list(config['product_lines'].keys())
        predicted_lines = set()
        for img in st.session_state.uploaded_images:
            line, conf = classify_image(img, product_line_names)
            if conf > 0.25:
                predicted_lines.add(line)
        if predicted_lines:
            st.success(f"图片识别产品线: {', '.join(predicted_lines)}")
            for line in predicted_lines:
                auto_keywords.extend(config['product_lines'][line]['search'])
            auto_keywords = list(set(auto_keywords))
        else:
            st.warning("无法自动识别产品线，将仅使用手动关键词")

    if manual_keywords.strip():
        manual_list = [k.strip() for k in manual_keywords.splitlines() if k.strip()]
        final_keywords = list(set(auto_keywords + manual_list))
    else:
        final_keywords = auto_keywords

    if final_keywords:
        st.text(f"最终搜索词数量: {len(final_keywords)}")
        with st.expander("查看搜索词"):
            st.write(final_keywords)

    st.markdown("---")
    st.caption("已排除公司域名数: " + str(len(st.session_state.excluded_domains)))
    if st.button("清空排除列表，重新开始"):
        st.session_state.excluded_domains.clear()
        st.session_state.search_count = 0
        st.rerun()

# ==================== 搜索主逻辑 ====================
def search_and_collect_leads(keywords, config, excluded_domains, user_features=None, max_new=5):
    new_leads = []
    seen_domains = excluded_domains.copy()
    region = config.get("region", "us-en")

    queries = []
    for kw in keywords:
        role = random.choice(config['role_words'])
        queries.append(f"{kw} {role}")
    random.shuffle(queries)

    for q in queries:
        if len(new_leads) >= max_new:
            break
        urls = duckduckgo_search(q, region=region, max_results=5)
        for url in urls:
            domain = urlparse(url).netloc
            if domain in seen_domains:
                continue
            html = fetch_page(url)
            if not html:
                continue
            info = extract_info(html, url, config['exclude_words'], keywords)
            if not info:
                seen_domains.add(domain)
                continue
            if user_features is not None:
                img_urls = get_website_images(html, url, max_images=3)
                sim, best_img = compute_similarity(user_features, img_urls)
                info['相似度'] = f"{sim*100:.1f}%"
                info['网站图片'] = best_img
            else:
                info['相似度'] = "未启用"
                info['网站图片'] = None
            matched_kw = [kw for kw in keywords if kw.lower() in html.lower()]
            info['匹配产品'] = ', '.join(matched_kw[:3]) if matched_kw else "通用匹配"
            new_leads.append(info)
            seen_domains.add(domain)
            if len(new_leads) >= max_new:
                break
        time.sleep(1)
    return new_leads

if st.button("🔍 搜索5家新公司", type="primary"):
    if not final_keywords:
        st.error("请至少上传图片或输入关键词")
    elif not cities:
        st.error("请至少选择一个城市")
    else:
        with st.spinner("正在搜索客户并分析图片相似度..."):
            leads = search_and_collect_leads(
                final_keywords, config,
                st.session_state.excluded_domains,
                st.session_state.user_image_features,
                max_new=5
            )
        if leads:
            st.session_state.search_count += 1
            st.session_state['last_leads'] = leads
            for lead in leads:
                domain = urlparse(lead['官网']).netloc
                st.session_state.excluded_domains.add(domain)
            st.success(f"第 {st.session_state.search_count} 次搜索，找到 {len(leads)} 家新公司")
        else:
            st.warning("未找到新公司，请尝试更换关键词或城市。")

if 'last_leads' in st.session_state:
    leads = st.session_state.last_leads
    for i, lead in enumerate(leads, 1):
        with st.container():
            st.subheader(f"{i}. {lead['公司名称']}")
            st.markdown(f"🌐 官网: [{lead['官网']}]({lead['官网']})")
            st.markdown(f"🔧 匹配产品: {lead['匹配产品']}")
            st.markdown(f"📞 联系方式: {lead['联系方式']}")

            if lead.get('网站图片'):
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    if st.session_state.uploaded_images:
                        st.image(st.session_state.uploaded_images[0], caption="你的产品", width=200)
                with col2:
                    st.image(lead['网站图片'], caption=f"客户网站图片", width=200)
                with col3:
                    st.metric("图片相似度", lead.get('相似度', 'N/A'))
            else:
                st.caption("未找到可对比的产品图片")
            st.markdown("---")

    df = pd.DataFrame(leads)
    df = df[['公司名称', '官网', '匹配产品', '联系方式', '相似度']]
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下载本次结果 CSV", csv, f"leads_{st.session_state.search_count}.csv", "text/csv")
else:
    st.info("点击上方按钮开始搜索，每次返回5家不重复的公司")
