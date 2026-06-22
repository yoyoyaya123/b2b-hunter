import streamlit as st
import requests
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from googlesearch import search
import PyPDF2
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="B2B全球精准获客-汽保工具", layout="wide")
st.title("🔧 汽车维修专用工具 · 全球B2B精准客户搜索")

# ==================== 全球多语言产品线配置 ====================
COUNTRY_CONFIG = {
    "德国": {
        "lang": "de", "country": "de",
        "cities": ["Berlin", "Hamburg", "München", "Frankfurt", "Stuttgart", "Köln", "Düsseldorf"],
        "role_words": ["Großhandel", "Großhändler", "Importeur", "Import", "Distributor", "Händler", "Lieferant", "Fachhandel"],
        "exclude_words": ["Werkstatt", "Reparatur", "Service-Center", "Autohaus", "Reifenservice", "Karosseriebau", "Lackiererei", "Tuning", "Industrie", "Baumaschinen", "Gartengeräte", "Landwirtschaft"],
        "product_lines": {
            "1. 空调/冷却系统": {
                "search": ["Kühlsystem-Dichtheitsprüfer", "Klimaservice-Werkzeug", "Klimaanlagen-Reparaturwerkzeug", "Kältemittel-Füllschlauch", "Klima-Lecksuchgerät"],
                "evidence": ["Kühlsystem-Dichtheitsprüfer", "Klimaservice-Werkzeug", "Klimaanlagen-Reparaturwerkzeug", "Kältemittel", "Klima-Lecksuchgerät", "Klimaservice-Station"]
            },
            "2. 仪表检测工具": {
                "search": ["Zylinderdruckprüfer", "Kraftstoffdruckmessgerät", "Dieseleinspritzung-Tester", "Motor-Diagnosegerät", "Unterdruckmanometer", "Abgasgegendruckprüfer"],
                "evidence": ["Zylinderdruckprüfer", "Kraftstoffdruckmessgerät", "Dieseleinspritzung-Tester", "Motor-Diagnosegerät", "Kompressionstester", "Einspritzdüsen-Tester"]
            },
            "3. 刹车/底盘/结构": {
                "search": ["Bremskolbenrückstellsatz", "Fahrwerk-Reparaturwerkzeug", "Kugelgelenkabzieher", "Kupplungszentrierwerkzeug", "Radlager-Abzieher-Set", "Stoßdämpfer-Montagewerkzeug"],
                "evidence": ["Bremskolbenrückstellsatz", "Fahrwerk-Reparaturwerkzeug", "Kugelgelenkabzieher", "Kupplungszentrierwerkzeug", "Radlager-Abzieher", "Stoßdämpfer-Montagewerkzeug"]
            },
            "4. 液体更换/系统维护": {
                "search": ["Bremsenentlüftungsgerät", "Kühlmittel-Befüllset", "Bremsflüssigkeitswechsler", "Kältemittelöl-Einfüllwerkzeug", "Absaug- und Einfüllspritze"],
                "evidence": ["Bremsenentlüftungsgerät", "Kühlmittel-Befüllset", "Bremsflüssigkeitswechsler", "Kältemittelöl-Einfüllwerkzeug", "Absaugspritze", "Entlüftungsgerät"]
            },
            "5. 内饰撬棒/卡扣耗材": {
                "search": ["Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set", "Innenraum-Demontagewerkzeug", "Öldichtungs-Haken-Set", "Schlauchklemmen-Zangen-Set"],
                "evidence": ["Kunststoff-Nylon-Hebel-Set", "Auto-Clip-Set", "Innenraum-Demontagewerkzeug", "Öldichtungs-Haken-Set", "Schlauchklemmen-Zangen-Set", "Verkleidungs-Clip"]
            }
        }
    },
    "法国": {
        "lang": "fr", "country": "fr",
        "cities": ["Paris", "Lyon", "Marseille", "Lille", "Bordeaux", "Toulouse", "Nantes"],
        "role_words": ["grossiste", "importateur", "distributeur", "fournisseur", "revendeur"],
        "exclude_words": ["garage", "atelier de réparation", "carrosserie", "peinture", "pneumatique", "industriel", "bâtiment", "jardinage", "agricole"],
        "product_lines": {
            "1. 空调/冷却系统": {
                "search": ["détecteur de fuite de radiateur", "outil de climatisation auto", "manifold frigorifique", "kit de charge de réfrigérant", "détecteur de fuite de clim"],
                "evidence": ["détecteur de fuite de radiateur", "outil de climatisation", "manifold frigorifique", "kit de charge", "détecteur de fuite de clim"]
            },
            "2. 仪表检测工具": {
                "search": ["testeur de compression", "manomètre de pression d'essence", "testeur d'injecteur diesel", "outil de diagnostic moteur", "dépressiomètre", "testeur de contre-pression"],
                "evidence": ["testeur de compression", "manomètre de pression d'essence", "testeur d'injecteur diesel", "diagnostic moteur", "dépressiomètre"]
            },
            "3. 刹车/底盘/结构": {
                "search": ["kit de repose-culasse", "outil de réparation de suspension", "extracteur de rotule", "outil de centrage d'embrayage", "extracteur de roulement", "outil de montage d'amortisseur"],
                "evidence": ["repose-culasse", "outil de suspension", "extracteur de rotule", "centrage d'embrayage", "extracteur de roulement"]
            },
            "4. 液体更换/系统维护": {
                "search": ["purgeur de frein", "kit de remplissage de liquide de refroidissement", "échangeur de liquide de frein", "outil de remplissage d'huile de réfrigérant", "seringue d'aspiration et de remplissage"],
                "evidence": ["purgeur de frein", "remplissage de liquide de refroidissement", "échangeur de liquide de frein", "seringue d'aspiration"]
            },
            "5. 内饰撬棒/卡扣耗材": {
                "search": ["kit de leviers en nylon", "kit de clips auto", "outil de démontage intérieur", "kit de crochets à joint", "kit de pinces pour colliers"],
                "evidence": ["leviers en nylon", "clips auto", "démontage intérieur", "crochets à joint", "pinces pour colliers"]
            }
        }
    },
    "西班牙": {
        "lang": "es", "country": "es",
        "cities": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao", "Zaragoza"],
        "role_words": ["mayorista", "importador", "distribuidor", "proveedor", "comercio al por mayor"],
        "exclude_words": ["taller", "reparación", "carrocería", "pintura", "neumáticos", "industrial", "construcción", "jardinería", "agrícola"],
        "product_lines": {
            "1. 空调/冷却系统": {
                "search": ["probador de fugas de radiador", "herramienta de climatización", "manómetro de refrigerante", "kit de carga de refrigerante", "detector de fugas de aire acondicionado"],
                "evidence": ["probador de fugas de radiador", "herramienta de climatización", "manómetro de refrigerante", "kit de carga", "detector de fugas"]
            },
            "2. 仪表检测工具": {
                "search": ["comprobador de compresión", "manómetro de presión de combustible", "probador de inyectores diésel", "herramienta de diagnóstico del motor", "vacuómetro", "probador de contrapresión"],
                "evidence": ["comprobador de compresión", "manómetro de presión", "probador de inyectores", "diagnóstico del motor"]
            },
            "3. 刹车/底盘/结构": {
                "search": ["juego de retroceso de freno", "herramienta de reparación de suspensión", "extractor de rótulas", "herramienta de centrado de embrague", "extractor de rodamientos", "montador de amortiguadores"],
                "evidence": ["retroceso de freno", "herramienta de suspensión", "extractor de rótulas", "centrado de embrague", "extractor de rodamientos"]
            },
            "4. 液体更换/系统维护": {
                "search": ["purgador de frenos", "kit de llenado de refrigerante", "cambiador de líquido de frenos", "herramienta de llenado de aceite de refrigerante", "jeringa de aspiración y llenado"],
                "evidence": ["purgador de frenos", "llenado de refrigerante", "cambiador de líquido de frenos", "jeringa de aspiración"]
            },
            "5. 内饰撬棒/卡扣耗材": {
                "search": ["kit de palancas de nailon", "kit de clips de coche", "herramienta de desmontaje interior", "kit de ganchos para retenes", "kit de alicates para abrazaderas"],
                "evidence": ["palancas de nailon", "clips de coche", "desmontaje interior", "ganchos para retenes", "alicates para abrazaderas"]
            }
        }
    },
    "葡萄牙": {
        "lang": "pt", "country": "pt",
        "cities": ["Lisboa", "Porto", "Braga", "Coimbra", "Faro"],
        "role_words": ["grossista", "importador", "distribuidor", "fornecedor", "revendedor"],
        "exclude_words": ["oficina", "reparação", "carroçaria", "pintura", "pneus", "industrial", "construção", "jardinagem", "agrícola"],
        "product_lines": {
            "1. 空调/冷却系统": {
                "search": ["detector de fugas de radiador", "ferramenta de ar condicionado", "manifold de refrigerante", "kit de carga de refrigerante", "detector de fugas de AC"],
                "evidence": ["detector de fugas", "ferramenta de ar condicionado", "manifold de refrigerante", "kit de carga"]
            },
            "2. 仪表检测工具": {
                "search": ["testador de compressão", "manómetro de pressão de combustível", "testador de injetores diesel", "ferramenta de diagnóstico do motor", "vacuómetro", "testador de contrapressão"],
                "evidence": ["testador de compressão", "manómetro de pressão", "testador de injetores", "diagnóstico do motor"]
            },
            "3. 刹车/底盘/结构": {
                "search": ["kit de recuo do travão", "ferramenta de reparação de suspensão", "extrator de rótulas", "ferramenta de centragem da embraiagem", "extrator de rolamentos", "montador de amortecedores"],
                "evidence": ["recuo do travão", "ferramenta de suspensão", "extrator de rótulas", "centragem da embraiagem"]
            },
            "4. 液体更换/系统维护": {
                "search": ["purga de travões", "kit de enchimento de líquido de refrigeração", "trocador de fluido de travões", "ferramenta de enchimento de óleo de refrigerante", "seringa de aspiração e enchimento"],
                "evidence": ["purga de travões", "enchimento de líquido", "trocador de fluido", "seringa de aspiração"]
            },
            "5. 内饰撬棒/卡扣耗材": {
                "search": ["kit de alavancas de nylon", "kit de clips automóvel", "ferramenta de desmontagem interior", "kit de ganchos para retentores", "kit de alicates para braçadeiras"],
                "evidence": ["alavancas de nylon", "clips automóvel", "desmontagem interior", "ganchos para retentores"]
            }
        }
    },
    "意大利": {
        "lang": "it", "country": "it",
        "cities": ["Milano", "Roma", "Napoli", "Torino", "Bologna", "Firenze"],
        "role_words": ["grossista", "importatore", "distributore", "fornitore", "rivenditore"],
        "exclude_words": ["officina", "riparazione", "carrozzeria", "verniciatura", "pneumatici", "industriale", "edilizia", "giardinaggio", "agricoltura"],
        "product_lines": {
            "1. 空调/冷却系统": {
                "search": ["tester perdite radiatore", "attrezzo per aria condizionata", "manifold refrigerante", "kit di ricarica refrigerante", "rilevatore perdite AC"],
                "evidence": ["tester perdite", "attrezzo per aria condizionata", "manifold refrigerante", "kit di ricarica"]
            },
            "2. 仪表检测工具": {
                "search": ["tester di compressione", "manometro pressione carburante", "tester iniettori diesel", "strumento di diagnosi motore", "vacuometro", "tester di contropressione"],
                "evidence": ["tester di compressione", "manometro pressione", "tester iniettori", "diagnosi motore"]
            },
            "3. 刹车/底盘/结构": {
                "search": ["kit rientro pistoncini freno", "attrezzo per sospensioni", "estrattore giunti sferici", "centraggio frizione", "estrattore cuscinetti", "montatore ammortizzatori"],
                "evidence": ["rientro pistoncini", "attrezzo per sospensioni", "estrattore giunti", "centraggio frizione"]
            },
            "4. 液体更换/系统维护": {
                "search": ["spurgo freni", "kit di riempimento liquido raffreddamento", "cambiatore liquido freni", "attrezzo riempimento olio refrigerante", "siringa aspirazione e riempimento"],
                "evidence": ["spurgo freni", "riempimento liquido", "cambiatore liquido", "siringa aspirazione"]
            },
            "5. 内饰撬棒/卡扣耗材": {
                "search": ["set leve in nylon", "set clip auto", "attrezzo smontaggio interni", "set ganci per guarnizioni", "set pinze per fascette"],
                "evidence": ["leve in nylon", "clip auto", "smontaggio interni", "ganci per guarnizioni"]
            }
        }
    },
    "英国": {
        "lang": "en", "country": "uk",
        "cities": ["London", "Birmingham", "Manchester", "Glasgow", "Liverpool", "Bristol"],
        "role_words": ["wholesaler", "importer", "distributor", "supplier"],
        "exclude_words": ["garage", "repair", "body shop", "paint", "tyre", "industrial", "construction", "garden", "agricultural"],
        "product_lines": {
            "1. 空调/冷却系统": {
                "search": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit", "AC leak detector"],
                "evidence": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit"]
            },
            "2. 仪表检测工具": {
                "search": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic tool", "vacuum gauge", "exhaust back pressure tester"],
                "evidence": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic"]
            },
            "3. 刹车/底盘/结构": {
                "search": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment tool", "bearing puller", "shock absorber mounting tool"],
                "evidence": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment"]
            },
            "4. 液体更换/系统维护": {
                "search": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "refrigerant oil fill tool", "suction and fill syringe"],
                "evidence": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "suction syringe"]
            },
            "5. 内饰撬棒/卡扣耗材": {
                "search": ["nylon pry bar set", "car clip set", "interior trim removal tool", "oil seal hook set", "hose clamp pliers set"],
                "evidence": ["nylon pry bar set", "car clip set", "interior trim removal", "oil seal hook", "hose clamp pliers"]
            }
        }
    },
    "美国": {
        "lang": "en", "country": "us",
        "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Miami", "Dallas"],
        "role_words": ["wholesaler", "importer", "distributor", "supplier"],
        "exclude_words": ["garage", "repair", "body shop", "paint", "tire", "industrial", "construction", "garden", "agricultural"],
        "product_lines": {
            "1. 空调/冷却系统": {
                "search": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit", "AC leak detector"],
                "evidence": ["radiator leak tester", "air conditioning service tool", "refrigerant manifold", "refrigerant charge kit"]
            },
            "2. 仪表检测工具": {
                "search": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic tool", "vacuum gauge", "exhaust back pressure tester"],
                "evidence": ["compression tester", "fuel pressure gauge", "diesel injector tester", "engine diagnostic"]
            },
            "3. 刹车/底盘/结构": {
                "search": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment tool", "bearing puller", "shock absorber mounting tool"],
                "evidence": ["brake piston wind-back kit", "suspension repair tool", "ball joint puller", "clutch alignment"]
            },
            "4. 液体更换/系统维护": {
                "search": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "refrigerant oil fill tool", "suction and fill syringe"],
                "evidence": ["brake bleeder", "coolant fill set", "brake fluid exchanger", "suction syringe"]
            },
            "5. 内饰撬棒/卡扣耗材": {
                "search": ["nylon pry bar set", "car clip set", "interior trim removal tool", "oil seal hook set", "hose clamp pliers set"],
                "evidence": ["nylon pry bar set", "car clip set", "interior trim removal", "oil seal hook", "hose clamp pliers"]
            }
        }
    }
}

# ==================== 辅助函数 ====================
def render_pdf_previews(pdf_file):
    try:
        pdf_file.seek(0)
        images = convert_from_bytes(pdf_file.read(), dpi=150)
        return images
    except:
        return None

def ocr_from_images(images):
    try:
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img, lang='eng+chi_sim+deu+fra+spa+por+ita') + "\n"
        return text.strip()
    except:
        return "OCR失败"

def fetch_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, timeout=10, headers=headers)
        resp.raise_for_status()
        return resp.text
    except:
        return None

def contains_any(text, kw_list):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in kw_list)

def extract_lead(html, url, exclude_words, role_words, evidence_keywords):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()

    if contains_any(text, exclude_words):
        return None
    if not contains_any(text, role_words):
        return None
    if not contains_any(text, evidence_keywords):
        return None

    domain = urlparse(url).netloc
    company = soup.title.string.strip() if soup.title else domain

    emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
    emails = [e for e in emails if 'noreply' not in e and 'example' not in e]

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

    ecommerce = []
    if 'amazon' in html:
        ecommerce.append("Amazon")
    if 'ebay' in html:
        ecommerce.append("eBay")
    ecommerce_str = ", ".join(ecommerce) if ecommerce else "未发现"

    phones = re.findall(r'[\+\(]?[0-9][0-9 .\-\(\)]{7,}[0-9]', html)
    contact = "邮箱: " + (", ".join(emails) if emails else "无") + "; 电话: " + (phones[0] if phones else "官网表单")

    matched = [kw for kw in evidence_keywords if kw.lower() in text.lower()]
    return {
        '公司名称': company,
        '官网': url,
        '匹配产品': ', '.join(matched[:3]),
        '社媒': socials,
        '规模': '中小型',
        '电商渠道': ecommerce_str,
        '联系方式': contact,
    }

# ==================== 主界面 ====================
with st.sidebar:
    st.header("🌍 搜索配置")
    selected_country = st.selectbox("选择目标国家", list(COUNTRY_CONFIG.keys()))
    config = COUNTRY_CONFIG[selected_country]

    # 产品线勾选
    st.subheader("📦 勾选要搜索的产品线")
    selected_lines = []
    for line_name, line_data in config['product_lines'].items():
        if st.checkbox(line_name, value=True):
            selected_lines.append(line_name)

    # 城市
    cities = st.multiselect("选择城市", config['cities'], default=config['cities'][:3])

    # PDF 上传与预览
    with st.expander("📄 上传产品目录PDF（辅助确认关键词）"):
        pdf_file = st.file_uploader("选择PDF文件", type=["pdf"])
        manual_keywords = st.text_area(
            "手动输入搜索关键词（每行一个，将覆盖产品线选择）",
            value="",
            placeholder="例如：Bremskolbenrückstellsatz\nZylinderdruckprüfer",
            height=80
        )
        if pdf_file:
            images = render_pdf_previews(pdf_file)
            if images:
                st.success(f"已加载 {len(images)} 页")
                for i, img in enumerate(images):
                    st.image(img, caption=f"第 {i+1} 页", width=300)
                ocr_text = ocr_from_images(images)
                st.text_area("OCR提取文字参考", value=ocr_text, height=100)
            else:
                st.error("PDF渲染失败")

if st.button("🚀 开始搜索", type="primary"):
    if not selected_lines and not manual_keywords.strip():
        st.error("请至少勾选一条产品线或手动输入关键词")
    elif not cities:
        st.error("请至少选择一个城市")
    else:
        # 确定最终搜索关键词和证据关键词
        if manual_keywords.strip():
            search_keywords = [k.strip() for k in manual_keywords.splitlines() if k.strip()]
            evidence_keywords = []
            for line in config['product_lines'].values():
                evidence_keywords.extend(line['evidence'])
        else:
            search_keywords = []
            evidence_keywords = []
            for line_name in selected_lines:
                line = config['product_lines'][line_name]
                search_keywords.extend(line['search'])
                evidence_keywords.extend(line['evidence'])

        # 生成搜索查询
        queries = []
        for kw in search_keywords:
            for role in random.sample(config['role_words'], min(2, len(config['role_words']))):
                for city in cities:
                    queries.append(f"{kw} {role} {city}")

        st.info(f"共 {len(queries)} 组搜索任务，请稍候...")
        all_leads = []
        seen = set()
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, q in enumerate(queries):
            status_text.text(f"正在搜索: {q}")
            progress_bar.progress((i+1)/len(queries))
            try:
                results = search(q, num=5, stop=5, user_agent='Mozilla/5.0',
                                 lang=config['lang'], country=config['country'])
            except Exception:
                time.sleep(2)
                continue

            for url in results:
                domain = urlparse(url).netloc
                if domain in seen:
                    continue
                seen.add(domain)
                html = fetch_page(url)
                if not html:
                    continue
                lead = extract_lead(html, url, config['exclude_words'], config['role_words'], evidence_keywords)
                if lead:
                    all_leads.append(lead)
                time.sleep(random.uniform(2, 5))  # 控制频率
            time.sleep(3)

        progress_bar.empty()
        status_text.empty()

        if not all_leads:
            st.warning("未找到匹配客户。请尝试减少城市或更换关键词。")
        else:
            unique_leads = []
            names = set()
            for l in all_leads:
                if l['公司名称'] not in names:
                    names.add(l['公司名称'])
                    unique_leads.append(l)
            final = unique_leads[:5]

            st.success(f"找到 {len(unique_leads)} 家匹配公司，显示前 5 家。")
            for i, lead in enumerate(final, 1):
                with st.container():
                    st.subheader(f"{i}. {lead['公司名称']}")
                    st.markdown(f"🌐 官网: [{lead['官网']}]({lead['官网']})")
                    social_links = []
                    for name, link in lead['社媒']:
                        if name and link.startswith('http'):
                            social_links.append(f"[{name}]({link})")
                        else:
                            social_links.append(link)
                    st.markdown(f"📱 社媒: {' · '.join(social_links)}")
                    st.markdown(f"🔧 匹配产品: {lead['匹配产品']}")
                    st.markdown(f"🏢 规模: {lead['规模']} | 🛒 电商: {lead['电商渠道']}")
                    st.markdown(f"📞 联系方式: {lead['联系方式']}")
                    st.markdown("---")

            df = pd.DataFrame(final)
            df['社媒'] = df['社媒'].apply(lambda x: '; '.join([f"{n}: {l}" for n, l in x]) if isinstance(x, list) else x)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载结果 CSV", csv, "global_leads.csv", "text/csv")
