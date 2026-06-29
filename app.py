import streamlit as st
import requests
import re
import time
import random
import pandas as pd
import json
import os
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ddgs import DDGS
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="JYTOOL 全球 B2B 精准获客与 CRM 系统", layout="wide")

# ==================== 数据库引擎 (带配置永久保存功能) ====================
class DatabaseManager:
    def __init__(self):
        self.use_gsheets = False
        self.client = None
        self.sheet = None
        self.client_cols = ["客户ID", "公司名", "官网", "邮箱", "联系方式", "匹配产品", "国家", "状态", "添加时间"]
        self.email_cols = ["邮件ID", "客户公司", "收件人", "发送时间", "主题", "内容摘要", "状态"]
        self.config_cols = ["配置项", "配置值"] # 新增配置表
        self._init_connection()

    def _init_connection(self):
        if "gcp_service_account" in st.secrets and "gsheets_url" in st.secrets:
            try:
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
                self.client = gspread.authorize(creds)
                self.sheet = self.client.open_by_url(st.secrets["gsheets_url"])
                
                worksheets = [ws.title for ws in self.sheet.worksheets()]
                if "Clients" not in worksheets:
                    self.sheet.add_worksheet(title="Clients", rows="1000", cols="20").append_row(self.client_cols)
                if "Emails" not in worksheets:
                    self.sheet.add_worksheet(title="Emails", rows="1000", cols="20").append_row(self.email_cols)
                if "Config" not in worksheets:
                    self.sheet.add_worksheet(title="Config", rows="50", cols="5").append_row(self.config_cols)
                    
                self.use_gsheets = True
            except Exception as e:
                print(f"云端数据库连接失败，原因: {e}")
                self.use_gsheets = False
        
        if not self.use_gsheets:
            if not os.path.exists("db_clients.csv"): pd.DataFrame(columns=self.client_cols).to_csv("db_clients.csv", index=False)
            if not os.path.exists("db_emails.csv"): pd.DataFrame(columns=self.email_cols).to_csv("db_emails.csv", index=False)
            if not os.path.exists("db_config.csv"): pd.DataFrame(columns=self.config_cols).to_csv("db_config.csv", index=False)

    def get_clients(self):
        if self.use_gsheets:
            try: return pd.DataFrame(self.sheet.worksheet("Clients").get_all_records())
            except: pass
        try: return pd.read_csv("db_clients.csv")
        except: return pd.DataFrame(columns=self.client_cols)

    def add_client(self, client_data):
        clean_data = {k: client_data.get(k, "") for k in self.client_cols}
        if self.use_gsheets:
            try: self.sheet.worksheet("Clients").append_row(list(clean_data.values())); return
            except: pass
        pd.DataFrame([clean_data]).to_csv("db_clients.csv", mode='a', header=False, index=False)

    def delete_client(self, client_id):
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Clients")
                cell = worksheet.find(client_id)
                if cell: worksheet.delete_rows(cell.row)
                return
            except: pass
        if os.path.exists("db_clients.csv"):
            try:
                df = pd.read_csv("db_clients.csv")
                df[df['客户ID'] != client_id].to_csv("db_clients.csv", index=False)
            except: pass

    def get_existing_urls_and_domains(self):
        urls, domains = set(), set()
        try:
            df = self.get_clients()
            if not df.empty and '官网' in df.columns:
                for u in df['官网'].dropna():
                    u = str(u).strip()
                    urls.add(u)
                    if u.startswith('http'): domains.add(urlparse(u).netloc.lower())
        except: pass
        return urls, domains

    def get_emails(self):
        if self.use_gsheets:
            try: return pd.DataFrame(self.sheet.worksheet("Emails").get_all_records())
            except: pass
        try: return pd.read_csv("db_emails.csv")
        except: return pd.DataFrame(columns=self.email_cols)

    def log_email(self, email_data):
        clean_data = {k: email_data.get(k, "") for k in self.email_cols}
        if self.use_gsheets:
            try: self.sheet.worksheet("Emails").append_row(list(clean_data.values())); return
            except: pass
        pd.DataFrame([clean_data]).to_csv("db_emails.csv", mode='a', header=False, index=False)

    def get_config(self):
        if self.use_gsheets:
            try:
                records = self.sheet.worksheet("Config").get_all_records()
                return {str(r['配置项']): str(r['配置值']) for r in records}
            except: pass
        try:
            df = pd.read_csv("db_config.csv")
            return dict(zip(df['配置项'], df['配置值']))
        except: return {}

    def save_config(self, conf_dict):
        rows = [self.config_cols] + [[str(k), str(v)] for k, v in conf_dict.items()]
        if self.use_gsheets:
            try:
                ws = self.sheet.worksheet("Config")
                ws.clear()
                ws.append_rows(rows)
                return
            except: pass
        pd.DataFrame(list(conf_dict.items()), columns=self.config_cols).to_csv("db_config.csv", index=False)

db = DatabaseManager()

# ==================== 本地缓存与启动加载 ====================
if 'config_loaded' not in st.session_state:
    saved_conf = db.get_config()
    st.session_state.update(saved_conf)
    st.session_state['config_loaded'] = True

if 'all_leads' not in st.session_state:
    st.session_state.all_leads = []
    st.session_state.excluded_domains = set()
    st.session_state.local_reports = {}
    st.session_state.current_page = 0

# ==================== 黑名单与配置库 (极致优化版) ====================
PLATFORM_BLOCKLIST = [
    "iqsdirectory.", "directory.", "yellowpages.", "thomasnet.", "kompass.", "europages.", "yelp.", "zoominfo.", "dnb.", "manta.", "crunchbase.", "trade.", "b2b.", "globalsources.", "made-in-china.", "alibaba.", "aliexpress.", "indiamart.", "tradekey.", "hktdc.", "amazon.", "ebay.", "walmart.", "shopee.", "lazada.", "etsy.", "wayfair.", "temu.", "shein.", "trustpilot.", "autozone.", "oreillyauto.", "napaonline.", "advanceautoparts.", "halfords.", "grainger.", "fastenal.", "mscdirect.", "homedepot.", "lowes.", "menards.", "target.", "costco.", "vevor.", "harborfreight.", "prices.", ".cn", ".com.cn"
]

CHINA_GEO_BLOCKLIST = [
    "guangdong", "shenzhen", "guangzhou", "dongguan", "foshan", "zhongshan", "zhuhai", "zhejiang", "ningbo", "hangzhou", "yiwu", "wenzhou", "taizhou", "jinhua", "shaoxing", "jiangsu", "shanghai", "shandong", "qingdao", "jinan", "hebei", "henan", "beijing", "tianjin", "+86 ", "0086", "86-1", "86-0", "made in china", "china mainland", "mainland china", "chinese supplier"
]

# 严格排除：上市公司/大型集团/关联企业/终端店/钣喷/轮胎店/上门维修
STRICT_BUSINESS_BLOCKLIST = [
    "investor relations", "stock symbol", "shareholders", "annual report", "subsidiary of", "listed company", "nasdaq", "nyse", "group of companies", "holdings", "plc", "ltd group",
    "retail store", "retail only", "auto repair shop", "repair service", "body shop", "car wash", "tyre shop", "tire shop", "mechanic service", "mobile mechanic", "towing service", "collision center", "auto care clinic", "book an appointment", "schedule service", "taller mecánico", "centro de reparación", "chapa y pintura", "grúa", "автосервис", "ремонт авто", "шиномонтаж", "СТО"
]

# 严格排除：非汽车专用工具/纯重型设备（千斤顶等）
IRRELEVANT_INDUSTRIES_BLOCKLIST = [
    "garden tools", "lawn mower", "woodworking tools", "plumbing tools", "construction equipment", "agricultural machinery", "industrial supplies",
    "floor jack", "two-post lift", "car lift", "wheel balancer", "tire changer", "general hardware", "socket set only"
]

# 强制包含词 (B2B正向验证，必须包含以下其一才算批发商)
B2B_REQUIRED_KEYWORDS = ["wholesale", "distributor", "dealer", "trade account", "become a dealer", "b2b", "mayorista", "distribuidor", "importador", "trade strictly", "stockist"]

# 优化后的精准产品词（去除了撬棒和正时，增加了 specialty / kit 属性）
BASE_EN_PRODUCTS = {
    "01 仪表与诊断系统": {"search": ["automotive diagnostic specialty tools", "radiator pressure tester kit", "cylinder compression tester gauge"]}, 
    "02 液体更换/制动工具": {"search": ["pneumatic brake fluid bleeder kit", "automotive oil extractor tool", "brake caliper wind back specialty tool"]}, 
    "03 汽车空调专检": {"search": ["automotive a/c manifold gauge set", "ac leak detection kit auto", "refrigerant recovery automotive"]}
}
BASE_ES_PRODUCTS = {
    "01 仪表与诊断系统": {"search": ["kit de probador de presión de radiador", "comprobador de compresión automotriz", "herramientas especiales de diagnóstico"]}, 
    "02 液体更换/制动工具": {"search": ["purgador de frenos neumático", "extractor de aceite automotriz", "bomba de vacío automotriz"]}, 
    "03 汽车空调专检": {"search": ["manómetro de aire acondicionado automotriz", "kit de detección de fugas a/c", "recuperador de refrigerante automotriz"]}
}

COUNTRY_CONFIG = {
    "🇺🇸 美国 (USA)": {"region": "us-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇬🇧 英国 (UK)": {"region": "uk-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇲🇽 墨西哥 (Mexico)": {"region": "mx-es", "role_words": ["mayorista", "distribuidor", "importador", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
    "🇦🇪 中东地区 (UAE/沙特)": {"region": "ae-en", "search_suffix": "UAE OR Saudi Arabia OR Dubai", "role_words": ["wholesaler", "distributor", "importer", "equipment supplier"], "product_lines": BASE_EN_PRODUCTS},
    "🇩🇪 德国 (Germany)": {"region": "de-de", "role_words": ["Großhandel", "Importeur", "Distributor", "Händler"], "product_lines": {"01 仪表检测": {"search": ["Kühlsystem-Dichtheitsprüfer", "Kompressionstester"]}}},
    "🇪🇸 西班牙/南美大区": {"region": "es-es", "role_words": ["mayorista", "importador", "distribuidor", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
}

# 高转化率邮件模板 (PAS模型)
EMAIL_TEMPLATES = {
    "en": {
        "1. 强力破冰 - 避开中间商 (Direct Sourcing)": "Subject: Quick question about your {core_product} supply chain\n\nHi team at {company_name},\n\nI’ve been following your growth as an independent tool distributor. \n\nI know local margins are getting tighter due to domestic wholesalers adding their markups. We manufacture {core_product} and supply directly to regional distributors like you, allowing you to bypass the middlemen and instantly improve your margins by 20%.\n\nWe don't require massive MOQs to start. Would you be open to a quick video call next week so I can show you our production line and send a risk-free sample?\n\nBest regards,\n[Your Name]",
        "2. 痛点切入 - 品控与售后 (Quality & Returns)": "Subject: Reducing warranty claims on {core_product}\n\nHi team at {company_name},\n\nMany auto tool distributors complain about high return rates and poor after-sales support from general hardware suppliers.\n\nSince we strictly specialize in automotive diagnostic & maintenance tools (like {core_product}), every batch undergoes rigorous vehicle-match testing. This translates to near-zero return rates for your trade accounts.\n\nCould we arrange a small trial order (even just 1-2 cartons) this month so your mechanics can test the build quality firsthand?\n\nBest regards,\n[Your Name]",
        "3. 第二次跟进 - 视频验厂与背书 (Trust Building)": "Subject: Video: How we test {core_product} before shipping\n\nHi team,\n\nI didn't hear back, so I thought a visual might help. \n\nI recorded a short 30-second video of how our QA team tests the {core_product} before it ships out to our overseas distributors. (Insert Link: YouTube/Drive)\n\nWe take quality seriously because we only do B2B. If you have 5 minutes this week, I'd love to discuss how our specialty tool lineup can complement your current catalog.\n\nBest regards,\n[Your Name]",
        "4. 终极试探 - 寻找采购决策人 (The Breakup)": "Subject: Appropriate person for tool purchasing at {company_name}?\n\nHi,\n\nI’ve reached out a couple of times regarding direct factory sourcing for {core_product}. I don't want to clutter your inbox if this isn't your department.\n\nCould you kindly point me to the person who handles purchasing for specialty auto tools? \n\nIf you are currently locked in with a supplier and not looking for better margins right now, just let me know and I will close your file. Thanks!\n\nBest regards,\n[Your Name]"
    },
    "es": {
        "1. 强力破冰 - 避开中间商 (Direct Sourcing)": "Asunto: Pregunta rápida sobre su cadena de suministro de {core_product}\n\nHola equipo de {company_name},\n\nHe estado siguiendo su crecimiento como distribuidor de herramientas. \n\nSé que los márgenes locales son cada vez más ajustados debido a los intermediarios. Fabricamos {core_product} y suministramos directamente a importadores como ustedes. Evitar a los intermediarios puede mejorar sus márgenes en un 20% de inmediato.\n\nNo requerimos grandes cantidades mínimas (MOQ) para empezar. ¿Estaría abierto a una breve videollamada la próxima semana para mostrarle nuestra fábrica y enviarle una muestra sin compromiso?\n\nSaludos,\n[Tu Nombre]",
        "2. 痛点切入 - 品控与售后 (Quality & Returns)": "Asunto: Reducción de devoluciones en {core_product}\n\nHola equipo de {company_name},\n\nMuchos distribuidores se quejan de las altas tasas de devolución de los proveedores generales.\n\nComo nos especializamos estrictamente en herramientas automotrices (como {core_product}), cada lote se somete a rigurosas pruebas. Esto se traduce en cero dolores de cabeza para sus clientes.\n\n¿Podríamos organizar un pequeño pedido de prueba (incluso 1-2 cajas) este mes para que comprueben la calidad de primera mano?\n\nSaludos,\n[Tu Nombre]",
        "3. 第二次跟进 - 视频验厂与背书 (Trust Building)": "Asunto: Video: Cómo probamos {core_product} antes de enviar\n\nHola equipo,\n\nNo he recibido respuesta, así que pensé que un video ayudaría.\n\nGrabé un breve video de cómo nuestro equipo de calidad prueba {core_product} antes de enviarlo. (Enlace: YouTube/Drive)\n\nTomamos la calidad muy en serio porque solo trabajamos B2B. Si tienen 5 minutos esta semana, me encantaría hablar sobre cómo podemos complementar su catálogo.\n\nSaludos,\n[Tu Nombre]",
        "4. 终极试探 - 寻找采购决策人 (The Breakup)": "Asunto: ¿Persona adecuada para compras en {company_name}?\n\nHola,\n\nHe intentado comunicarme sobre el suministro directo de {core_product}. No quiero llenar su bandeja si este no es su departamento.\n\n¿Podría indicarme la persona encargada de compras de herramientas especiales?\n\nSi ya tienen un proveedor y no buscan mejores márgenes ahora, avíseme y cerraré su expediente. ¡Gracias!\n\nSaludos,\n[Tu Nombre]"
    }
}

def send_smtp_email(to_addr, subject, body):
    if not st.session_state.get('smtp_user') or not st.session_state.get('smtp_pass'): return False, "⚠️ 错误: 请先配置 SMTP 账号！"
    try:
        msg = MIMEMultipart()
        msg['From'] = st.session_state['smtp_user']
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(body + st.session_state.get('email_sign', ''), 'plain', 'utf-8'))
        smtp_port = int(st.session_state['smtp_port'])
        if smtp_port in [465, 994]: server = smtplib.SMTP_SSL(st.session_state['smtp_server'], smtp_port)
        else: server = smtplib.SMTP(st.session_state['smtp_server'], smtp_port); server.starttls()
        server.login(st.session_state['smtp_user'], st.session_state['smtp_pass'])
        server.send_message(msg)
        server.quit()
        return True, "发送成功"
    except Exception as e: return False, f"发送失败: {str(e)}"

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("🧭 系统导航")
    
    if db.use_gsheets: st.success("✅ 云数据库已连接 (客户记录与配置永久保存)")
    else: st.error("⚠️ 警告：当前使用云端临时缓存。网页刷新或休眠后【数据将丢失】！请参考文档配置 GSheets 密钥。")
    
    page = st.radio("请选择功能模块:", ["🔍 获客与开发工作台", "🗃️ 客户 CRM 数据库", "📨 发送追踪记录"])
    st.markdown("---")
    
    with st.expander("⚙️ 邮箱 SMTP 配置 (用于自动发信)", expanded=False):
        smtp_server = st.text_input("SMTP 服务器", value=st.session_state.get('smtp_server', 'smtp.gmail.com'))
        smtp_port = st.number_input("端口号", value=int(st.session_state.get('smtp_port', 587)))
        smtp_user = st.text_input("你的邮箱账号", value=st.session_state.get('smtp_user', ''))
        smtp_pass = st.text_input("邮箱授权码", type="password", value=st.session_state.get('smtp_pass', ''))
        email_sign = st.text_area("邮件签名", value=st.session_state.get('email_sign', '\n\nBest regards,\nSales Team'))
        if st.button("💾 永久保存发信配置"):
            conf = {'smtp_server': smtp_server, 'smtp_port': str(smtp_port), 'smtp_user': smtp_user, 'smtp_pass': smtp_pass, 'email_sign': email_sign}
            st.session_state.update(conf)
            db.save_config(conf)
            st.success("🎉 发信配置已永久保存入库！下次打开无需重新填写。")

    if page == "🔍 获客与开发工作台":
        st.markdown("---")
        st.header("🌍 深度搜索配置")
        selected_country = st.selectbox("🎯 选择目标国家", list(COUNTRY_CONFIG.keys()) + ["🌍 + 自定义其他国家 (自由配置)"])
        custom_name, custom_roles_list, custom_excludes_list = "", [], []
        if selected_country == "🌍 + 自定义其他国家 (自由配置)":
            st.info("💡 **上帝模式**")
            custom_name = st.text_input("1. 目标国家英文名", value="Australia")
            custom_roles = st.text_input("2. 经销商词汇", value="wholesaler, distributor, importer, supplier")
            config = {"region": "wt-wt", "search_suffix": custom_name, "role_words": [x.strip() for x in custom_roles.split(",")], "product_lines": BASE_EN_PRODUCTS}
            display_country_name = custom_name
        else:
            config = COUNTRY_CONFIG[selected_country]
            display_country_name = selected_country

        st.subheader("📦 选择侦测产品线")
        selected_lines = [line for line in config['product_lines'].keys() if st.checkbox(line, value=True)]
        manual_keywords = st.text_area("🔧 补充小语种产品词汇 (可选)", height=80)
        final_keywords = []
        for line in selected_lines: final_keywords.extend(config['product_lines'][line]['search'])
        if manual_keywords.strip(): final_keywords.extend([k.strip() for k in manual_keywords.splitlines() if k.strip()])
        final_keywords = list(set(final_keywords))

# 在搜索引擎底层强力排除C端网站
def duckduckgo_search(query, region, max_results=20):
    search_constraint = "-retail -repair -forum -blog -amazon -aliexpress -vevor"
    for q in [f'{query} {search_constraint}', query]:
        for backend in ['lite', 'html', 'api']:
            try:
                results = []
                with DDGS() as ddgs:
                    for r in ddgs.text(q, region=region, backend=backend, max_results=max_results): results.append(r['href'])
                if results: return results
            except: continue
    return []

# 二次验证：深度提取官网和社媒矩阵
def local_background_check(lead, country):
    soup = BeautifulSoup(lead['HTML内容'], 'html.parser')
    
    fb_links = list(set(re.findall(r'(https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+)', lead['HTML内容'])))
    in_links = list(set(re.findall(r'(https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9._-]+)', lead['HTML内容'])))
    ig_links = list(set(re.findall(r'(https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+)', lead['HTML内容'])))
    
    social_str = ""
    if in_links: social_str += f"💼 LinkedIn (查规模): {in_links[0]}\n"
    if fb_links: social_str += f"📘 Facebook (看门店/活动): {fb_links[0]}\n"
    if ig_links: social_str += f"📸 Instagram (看产品宣发): {ig_links[0]}\n"
    if not social_str: social_str = "⚠️ 未在官网提取到主要社交媒体，建议手动搜索其 LinkedIn 验证 B2B 属性。"

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    intro = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else "未能抓取到 Meta 描述。"
    
    return f"### 📊 资深业务员：{lead['公司名']} 客户背景深度调研\n**1. 官方网站**：{lead['官网']} (唯一有效入口)\n**2. 核心社媒矩阵 (二次验证)**：\n{social_str}\n**3. 官网介绍**：{intro[:300]}...\n**4. 关键人触达**：📥 发现邮箱：`{lead['邮箱']}`\n**5. 业务员分析指导**：由于已经过严格的 B2B 正向筛查，该公司极大概率属于区域性进口分销商。建议发送 [强力破冰 - 避开中间商] 模板切入。"

if page == "🔍 获客与开发工作台":
    st.title("🔧 获客与开发工作台 (全能深度版)")
    if st.button(f"🔍 强力深挖 5 家 【{display_country_name}】 顶级经销商", type="primary"):
        if not final_keywords: st.error("请先选择产品线！")
        else:
            scored_leads = []
            db_existing_urls, db_existing_domains = db.get_existing_urls_and_domains()
            seen = st.session_state.excluded_domains.copy() | db_existing_domains
            queries = [f'{kw} {random.choice(config["role_words"])} {config.get("search_suffix", "")}'.strip() for kw in final_keywords]
            random.shuffle(queries)
            progress_text = st.empty()
            
            with st.spinner("深挖中，正在进行B2B属性强制验证..."):
                for q in queries:
                    if len(scored_leads) >= 5: break
                    progress_text.write(f"🔄 正在深挖: `{q}` ({len(scored_leads)}/5)...")
                    urls = duckduckgo_search(q, region=config.get("region", "wt-wt"), max_results=15)
                    for url in urls:
                        if len(scored_leads) >= 5: break
                        domain = urlparse(url).netloc.lower()
                        if url in db_existing_urls or domain in seen or any(b in domain for b in PLATFORM_BLOCKLIST): continue
                        try:
                            html = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'}).text
                            soup = BeautifulSoup(html, 'html.parser')
                            text = soup.get_text().lower()
                            
                            # 1. 严格负向排除（查杀：上市公司、终端门店、重型举升设备等）
                            if any(x in text for x in CHINA_GEO_BLOCKLIST + STRICT_BUSINESS_BLOCKLIST + IRRELEVANT_INDUSTRIES_BLOCKLIST): 
                                continue
                            
                            # 2. 强效正向验证（二次验证：网页必须包含至少一个 B2B 批发商关键词）
                            if not any(b2b_kw in text for b2b_kw in B2B_REQUIRED_KEYWORDS):
                                continue
                                
                            matched = [kw for kw in final_keywords if kw.lower() in text]
                            if not matched: continue
                            
                            comp_name = soup.title.string.strip() if soup.title else domain
                            emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
                            
                            scored_leads.append({"客户ID": f"CUS_{int(time.time())}_{random.randint(100,999)}", "公司名": comp_name[:60], "官网": url, "邮箱": emails[0] if emails else "", "联系方式": " | ".join(emails[:2]) if emails else "表单", "匹配产品": matched[0], "国家": display_country_name, "状态": "未联系", "添加时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "HTML内容": html})
                            seen.add(domain)
                        except: pass
                    time.sleep(1)
            progress_text.empty()
            if scored_leads:
                st.session_state.all_leads.extend(scored_leads)
                st.session_state.excluded_domains = seen
                st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
                for l in scored_leads: db.add_client(l)
                st.success(f"🎉 成功筛选并斩获 {len(scored_leads)} 家全新优质 B2B 经销商，已存入 CRM 数据库！")
            else: st.warning("未发现符合严格B2B标准的新线索，请尝试更换产品线或重试。")

    if st.session_state.all_leads:
        total = len(st.session_state.all_leads)
        total_p = (total - 1) // 5 + 1
        cur_p = st.session_state.current_page
        c1, c2, c3 = st.columns([1, 1, 3])
        with c1:
            if st.button("⬅️ 上一页", disabled=(cur_p == 0)): st.session_state.current_page -= 1; st.rerun()
        with c2:
            if st.button("下一页 ➡️", disabled=(cur_p >= total_p - 1)): st.session_state.current_page += 1; st.rerun()
        with c3: st.write(f"第 {cur_p+1}/{total_p} 页 · 共 {total} 家客户")

        emails_df = db.get_emails()
        for i in range(cur_p * 5, min((cur_p + 1) * 5, total)):
            lead = st.session_state.all_leads[i]
            col_t, col_d = st.columns([5, 1])
            with col_t: st.subheader(f"{i+1}. {lead['公司名']}")
            with col_d:
                if st.button("🗑️ 移除此客户", key=f"del_{lead['客户ID']}"):
                    db.delete_client(lead['客户ID'])
                    st.session_state.all_leads = [l for l in st.session_state.all_leads if l['客户ID'] != lead['客户ID']]
                    st.rerun()
            st.markdown(f"**官网**: [{lead['官网']}]({lead['官网']}) | **核心匹配产品**: `{lead['匹配产品']}`")
            
            history_count = len(emails_df[emails_df['收件人'] == lead['邮箱']]) if not emails_df.empty and lead['邮箱'] else 0
            if history_count > 0: st.warning(f"🕒 **联系追踪**: 已对该客户发送过 **{history_count}** 次邮件")
            else: st.success("🆕 **联系追踪**: 暂无该客户的邮件沟通记录。")

            if lead['官网'] not in st.session_state.local_reports:
                if st.button(f"📊 生成深调档案 (官网+社媒)", key=f"bg_{i}"):
                    st.session_state.local_reports[lead['官网']] = local_background_check(lead, lead['国家'])
                    st.rerun()
            if lead['官网'] in st.session_state.local_reports:
                with st.expander("✅ 展开查看：背景调查报告", expanded=False): st.markdown(st.session_state.local_reports[lead['官网']])
            
            with st.expander("✉️ 展开开发信工作台 (撰写与发送)", expanded=True):
                lang = "es" if "Mexico" in lead['国家'] or "西班牙" in lead['国家'] else "en"
                c_ang, c_to = st.columns([2, 1])
                with c_ang: angle = st.selectbox("1️⃣ 选择开发跟进模板", list(EMAIL_TEMPLATES[lang].keys()), index=2 if history_count==1 else (3 if history_count>=2 else 0), key=f"ang_{i}")
                with c_to: target_email = st.text_input("收件人", value=lead['邮箱'], key=f"to_{i}")
                
                tpl = EMAIL_TEMPLATES[lang][angle].split("\n\n", 1)
                mail_sub = st.text_input("邮件主题", value=tpl[0].replace("Subject: ", "").replace("Asunto: ", "").format(company_name=lead['公司名'], core_product=lead['匹配产品']), key=f"sub_{i}")
                mail_body = st.text_area("邮件正文 (可自由修改)", value=tpl[1].format(company_name=lead['公司名'], core_product=lead['匹配产品']), height=200, key=f"body_{i}")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("🚀 立即 SMTP 发送", key=f"snd_{i}", type="primary"):
                        success, msg = send_smtp_email(target_email, mail_sub, mail_body)
                        if success:
                            st.success("✅ 邮件发送成功！")
                            db.log_email({"邮件ID": f"MAIL_{int(time.time())}", "客户公司": lead['公司名'], "收件人": target_email, "发送时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "主题": mail_sub, "内容摘要": mail_body[:50]+"...", "状态": "成功"})
                            st.rerun()
                        else: st.error(msg)
                with c3:
                    if st.button("🔖 仅标记为已手动发送", key=f"mrk_{i}"):
                        db.log_email({"邮件ID": f"MAIL_{int(time.time())}", "客户公司": lead['公司名'], "收件人": target_email, "发送时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "主题": mail_sub, "内容摘要": "(手动复制发送)", "状态": "手动标记"})
                        st.rerun()
            st.markdown("---")

elif page == "🗃️ 客户 CRM 数据库":
    st.title("🗃️ 客户中心")
    df = db.get_clients()
    search = st.text_input("🔍 搜索公司名")
    if not df.empty:
        if search: df = df[df['公司名'].str.contains(search, case=False)]
        st.dataframe(df, use_container_width=True)
        with st.expander("🗑️ 手动清理 CRM 中的无效客户"):
            del_id = st.text_input("请输入要删除的【客户ID】")
            if st.button("彻底删除", type="primary") and del_id:
                db.delete_client(del_id.strip()); st.rerun()
    else: st.info("数据库为空。")

elif page == "📨 发送追踪记录":
    st.title("📨 邮件发送追踪")
    df_logs = db.get_emails()
    if not df_logs.empty:
        st.dataframe(df_logs.sort_values(by="发送时间", ascending=False), use_container_width=True)
        st.download_button("📥 导出 CSV", df_logs.to_csv(index=False).encode('utf-8-sig'), "Email_Logs.csv", "text/csv")
    else: st.info("暂无记录。")
