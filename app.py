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

# 设置页面
st.set_page_config(page_title="JYTOOL 全球 B2B 精准获客与 CRM 系统", layout="wide")

# ==================== 数据库引擎 (带配置永久保存功能) ====================
class DatabaseManager:
    def __init__(self):
        self.use_gsheets = False
        self.client = None
        self.sheet = None
        self.client_cols = ["客户ID", "公司名", "官网", "邮箱", "联系方式", "匹配产品", "国家", "状态", "添加时间"]
        self.email_cols = ["邮件ID", "客户公司", "收件人", "发送时间", "主题", "内容摘要", "状态"]
        self.config_cols = ["配置项", "配置值"] 
        self.blacklist_cols = ["域名"]  # 新增：永久黑名单机制
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
                if "Blacklist" not in worksheets: # 新增：云端创建黑名单表
                    self.sheet.add_worksheet(title="Blacklist", rows="1000", cols="5").append_row(self.blacklist_cols)
                    
                self.use_gsheets = True
            except Exception as e:
                print(f"云端数据库连接失败，原因: {e}")
                self.use_gsheets = False
        
        if not self.use_gsheets:
            if not os.path.exists("db_clients.csv"): pd.DataFrame(columns=self.client_cols).to_csv("db_clients.csv", index=False)
            if not os.path.exists("db_emails.csv"): pd.DataFrame(columns=self.email_cols).to_csv("db_emails.csv", index=False)
            if not os.path.exists("db_config.csv"): pd.DataFrame(columns=self.config_cols).to_csv("db_config.csv", index=False)
            if not os.path.exists("db_blacklist.csv"): pd.DataFrame(columns=self.blacklist_cols).to_csv("db_blacklist.csv", index=False)

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

    def add_to_blacklist(self, domain):
        """【修复1】将没用/删除的域名拉入永久黑名单"""
        if not domain: return
        if self.use_gsheets:
            try: 
                self.sheet.worksheet("Blacklist").append_row([domain])
                return
            except: pass
        if os.path.exists("db_blacklist.csv"):
            try: pd.DataFrame([{"域名": domain}]).to_csv("db_blacklist.csv", mode='a', header=False, index=False)
            except: pass

    def delete_client(self, client_id):
        """【修复1】删除时，自动提取域名并永远拉黑拉黑"""
        try:
            df = self.get_clients()
            client_row = df[df['客户ID'] == client_id]
            if not client_row.empty:
                url = str(client_row.iloc[0].get('官网', '')).strip()
                if url.startswith('http'):
                    domain = urlparse(url).netloc.lower()
                    self.add_to_blacklist(domain) # 自动加入黑名单
        except: pass

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
        """【修复1】搜索时同时排查现有客户和黑名单中的客户"""
        urls, domains = set(), set()
        try:
            # 1. 现存的客户官网排除
            df = self.get_clients()
            if not df.empty and '官网' in df.columns:
                for u in df['官网'].dropna():
                    u = str(u).strip()
                    urls.add(u)
                    if u.startswith('http'): domains.add(urlparse(u).netloc.lower())
            
            # 2. 读取曾被删除的黑名单域名
            if self.use_gsheets:
                try:
                    bl_records = self.sheet.worksheet("Blacklist").get_all_records()
                    for r in bl_records: domains.add(str(r.get('域名', '')).strip().lower())
                except: pass
            else:
                if os.path.exists("db_blacklist.csv"):
                    bl_df = pd.read_csv("db_blacklist.csv")
                    if '域名' in bl_df.columns:
                        for d in bl_df['域名'].dropna(): domains.add(str(d).strip().lower())
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

    def update_client_status(self, client_id, new_status):
        """【修复2】更新客户状态 (发件成功后调用)"""
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Clients")
                cell = worksheet.find(client_id)
                if cell:
                    worksheet.update_cell(cell.row, 8, new_status) # 第8列是状态列
                return
            except Exception as e: print(f"GSheets 更新状态失败: {e}")
        
        if os.path.exists("db_clients.csv"):
            try:
                df = pd.read_csv("db_clients.csv")
                if client_id in df['客户ID'].values:
                    df.loc[df['客户ID'] == client_id, '状态'] = new_status
                    df.to_csv("db_clients.csv", index=False)
            except Exception as e: print(f"本地 CSV 更新状态失败: {e}")

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

# ==================== 黑名单与配置库 (黄金平衡版) ====================
PLATFORM_BLOCKLIST = [
    "iqsdirectory.", "directory.", "yellowpages.", "thomasnet.", "kompass.", "europages.", "yelp.", "zoominfo.", "dnb.", "manta.", "crunchbase.", "trade.", "b2b.", "globalsources.", "made-in-china.", "alibaba.", "aliexpress.", "indiamart.", "tradekey.", "hktdc.", "amazon.", "ebay.", "walmart.", "shopee.", "lazada.", "etsy.", "wayfair.", "temu.", "shein.", "trustpilot.", "autozone.", "oreillyauto.", "napaonline.", "advanceautoparts.", "halfords.", "grainger.", "fastenal.", "mscdirect.", "homedepot.", "lowes.", "menards.", "target.", "costco.", "vevor.", "harborfreight.", "prices.", ".cn", ".com.cn"
]

CHINA_GEO_BLOCKLIST = [
    "guangdong", "shenzhen", "guangzhou", "dongguan", "foshan", "zhongshan", "zhuhai", "zhejiang", "ningbo", "hangzhou", "yiwu", "wenzhou", "taizhou", "jinhua", "shaoxing", "jiangsu", "shanghai", "shandong", "qingdao", "jinan", "hebei", "henan", "beijing", "tianjin", "+86 ", "0086", "86-1", "86-0", "made in china", "china mainland", "mainland china", "chinese supplier"
]

STRICT_BUSINESS_BLOCKLIST = [
    "investor relations", "stock symbol", "shareholders", "annual report", "subsidiary of", "listed company", "nasdaq", "nyse", "holdings", "plc", "retail only"
]

IRRELEVANT_INDUSTRIES_BLOCKLIST = [
    "garden tools", "lawn mower", "woodworking tools", "plumbing tools", "agricultural machinery", "two-post lift", "wheel balancer"
]

B2B_REQUIRED_KEYWORDS = ["wholesale", "distributor", "dealer", "trade account", "become a dealer", "b2b", "mayorista", "distribuidor", "importador", "trade strictly", "stockist", "bulk supply"]

BASE_EN_PRODUCTS = {
    "01 仪表与诊断系统": {"search": ["radiator pressure tester", "cylinder compression tester", "automotive diagnostic tool"]}, 
    "02 液体更换/制动工具": {"search": ["brake bleeder kit", "oil extractor tool", "brake caliper wind back tool"]}, 
    "03 汽车空调专检": {"search": ["a/c manifold gauge set", "ac leak detection kit", "refrigerant recovery tool"]}
}
BASE_ES_PRODUCTS = {
    "01 仪表与诊断系统": {"search": ["probador de presión de radiador", "comprobador de compresión", "herramientas de diagnóstico automotriz"]}, 
    "02 液体更换/制动工具": {"search": ["purgador de frenos", "extractor de aceite", "bomba de vacío automotriz"]}, 
    "03 汽车空调专检": {"search": ["manómetro de aire acondicionado", "kit de detección de fugas a/c", "recuperador de refrigerante"]}
}

COUNTRY_CONFIG = {
    "🇺🇸 美国 (USA)": {"region": "us-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇬🇧 英国 (UK)": {"region": "uk-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇲🇽 墨西哥 (Mexico)": {"region": "mx-es", "role_words": ["mayorista", "distribuidor", "importador", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
    "🇦🇪 中东地区 (UAE/沙特)": {"region": "ae-en", "search_suffix": "UAE OR Saudi Arabia OR Dubai", "role_words": ["wholesaler", "distributor", "importer", "equipment supplier"], "product_lines": BASE_EN_PRODUCTS},
    "🇩🇪 德国 (Germany)": {"region": "de-de", "role_words": ["Großhandel", "Importeur", "Distributor", "Händler"], "product_lines": {"01 仪表检测": {"search": ["Kühlsystem-Dichtheitsprüfer", "Kompressionstester"]}}},
    "🇪🇸 西班牙/南美大区": {"region": "es-es", "role_words": ["mayorista", "importador", "distribuidor", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
}

# ==================== 全新外贸霸气开发信模板 (硬核工厂风) ====================
EMAIL_TEMPLATES = {
    "en": {
        "1. 海关数据截胡法 (直击底价/去中间商)": "Subject: Direct Factory Supply: {core_product} for {company_name}\n\nHi [Purchasing Manager/Team],\n\nI noticed {company_name} is actively importing auto tools into your market.\n\nMany distributors unknowingly buy {core_product} through 2nd or 3rd tier trading companies in China, losing at least 15-25% in profit margins. \n\nWe are the true source factory behind several top tool brands. By working with us directly, you get:\n- 100% Direct factory pricing (No middleman markup)\n- Strict QC & Fast OEM branding (Your Logo)\n\nCan I send you our direct-factory price list (Catalog) for {core_product} to compare with your current supplier?\n\nBest regards,\n[Your Name]",
        
        "2. 终端退货暴击法 (主打工业级/抗造品质)": "Subject: Stopping mechanic complaints about {core_product}\n\nHi team at {company_name},\n\nThe #1 complaint we hear from tool distributors is that cheap {core_product} breaks after a few uses, ruining your reputation with auto repair shops.\n\nWe solved this. Our {core_product} is forged with industrial-grade materials and strictly stress-tested for professional garage use. \n\n- Zero return rate from our current EU/US partners.\n- Reliable factory warranty.\n\nI’ve attached a quick video showing our stress test. Would you be open to receiving a trial sample to test the quality in your own warehouse?\n\nBest regards,\n[Your Name]",
        
        "3. 新品独家市场法 (制造稀缺与FOMO)": "Subject: New arrival: Upgraded {core_product} (Distributor Pricing)\n\nHi team,\n\nWe just launched an upgraded version of our {core_product}, designed specifically for modern vehicle models.\n\nWe are currently looking for 2-3 reliable distribution partners in your region to introduce this profitable line. \n\nWhy it sells fast:\n- Upgraded design saving mechanics 30% operation time.\n- Highly competitive wholesale margins for early partners.\n\nSince you are a leading tool supplier locally, you are on our top contact list. Do you have 5 minutes this week to see if we are a good fit?\n\nBest regards,\n[Your Name]",
        
        "4. 单刀直入算账法 (极简比价/要回复)": "Subject: Cut your {core_product} costs by 20%\n\nHi,\n\nI’ll get straight to the point.\n\nIf you are currently buying {core_product} from general hardware traders, you are likely overpaying. We are the source manufacturer. \n\nSwitching your {core_product} orders to us means:\n1. 20%+ better pricing immediately.\n2. Direct factory warranty and support.\n3. Custom packaging with YOUR brand.\n\nReply \"Yes\" and I will send you our B2B catalog and wholesale price list right now. \n\nBest regards,\n[Your Name]"
    },
    "es": {
        "1. 海关数据截胡法 (直击底价/去中间商)": "Asunto: Suministro directo de fábrica: {core_product} para {company_name}\n\nHola [Gerente de Compras/Equipo],\n\nNoté que {company_name} importa activamente herramientas automotrices en su mercado.\n\nMuchos distribuidores compran {core_product} a través de empresas intermediarias en China, perdiendo al menos un 15-25% de margen. \n\nSomos la fábrica de origen real detrás de varias marcas principales. Al trabajar directamente con nosotros, obtienen:\n- Precios 100% directos de fábrica (Sin intermediarios)\n- Estricto control de calidad y marca OEM (Su Logotipo)\n\n¿Puedo enviarles nuestra lista de precios directos de {core_product} para que comparen con su proveedor actual?\n\nSaludos,\n[Tu Nombre]",
        
        "2. 终端退货暴击法 (主打工业级/抗造品质)": "Asunto: Evite quejas de mecánicos sobre {core_product}\n\nHola equipo de {company_name},\n\nLa queja #1 de los distribuidores es que el {core_product} barato se rompe rápido, arruinando su reputación con los talleres mecánicos.\n\nHemos resuelto esto. Nuestro {core_product} está forjado con materiales de grado industrial y probado estrictamente para uso profesional.\n\n- Tasa de devolución cero de nuestros socios actuales.\n- Garantía de fábrica confiable.\n\nHe adjuntado un breve video mostrando nuestras pruebas. ¿Estarían abiertos a recibir una muestra de prueba para verificar la calidad?\n\nSaludos,\n[Tu Nombre]",
        
        "3. 新品独家市场法 (制造稀缺与FOMO)": "Asunto: Nueva llegada: {core_product} mejorado (Precios de Distribuidor)\n\nHola equipo,\n\nAcabamos de lanzar una versión mejorada de nuestro {core_product}, diseñada para vehículos modernos.\n\nActualmente buscamos 2-3 socios distribuidores confiables en su región para introducir esta línea rentable.\n\nPor qué se vende rápido:\n- Diseño mejorado que ahorra a los mecánicos un 30% de tiempo.\n- Márgenes mayoristas altamente competitivos para los primeros socios.\n\nComo son un proveedor líder local, están en nuestra lista principal. ¿Tienen 5 minutos esta semana para hablar?\n\nSaludos,\n[Tu Nombre]",
        
        "4. 单刀直入算账法 (极简比价/要回复)": "Asunto: Reduzca sus costos de {core_product} en un 20%\n\nHola,\n\nIré directo al grano.\n\nSi compran {core_product} a comerciantes generales, es probable que estén pagando de más. Somos el fabricante de origen.\n\nCambiar sus pedidos a nosotros significa:\n1. 20%+ mejores precios inmediatamente.\n2. Garantía y soporte directo de fábrica.\n3. Empaque personalizado con SU marca.\n\nResponda \"Sí\" y le enviaré nuestro catálogo B2B y lista de precios mayoristas ahora mismo.\n\nSaludos,\n[Tu Nombre]"
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
    
    if db.use_gsheets: st.success("✅ 云数据库已连接 (记录永久保存)")
    else: st.error("⚠️ 警告：当前使用云端临时缓存。网页刷新后数据将丢失！")
    
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
            st.success("🎉 发信配置已永久保存！")

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

def duckduckgo_search(query, region, max_results=20):
    search_constraint = "-amazon -aliexpress -vevor -ebay -walmart"
    for q in [f'{query} {search_constraint}', query]:
        for backend in ['lite', 'html', 'api']:
            try:
                results = []
                with DDGS() as ddgs:
                    for r in ddgs.text(q, region=region, backend=backend, max_results=max_results): results.append(r['href'])
                if results: return results
            except: continue
    return []

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
    return f"### 📊 资深业务员：{lead['公司名']} 客户背景深度调研\n**1. 官方网站**：{lead['官网']}\n**2. 核心社媒矩阵**：\n{social_str}\n**3. 官网介绍**：{intro[:300]}...\n**4. 关键人触达**：📥 发现邮箱：`{lead['邮箱']}`"

if page == "🔍 获客与开发工作台":
    st.title("🔧 获客与开发工作台 (精准强控版)")
    if st.button(f"🔍 强力深挖 5 家 【{display_country_name}】 顶级经销商", type="primary"):
        if not final_keywords: st.error("请先选择产品线！")
        else:
            scored_leads = []
            db_existing_urls, db_existing_domains = db.get_existing_urls_and_domains()
            seen = st.session_state.excluded_domains.copy() | db_existing_domains
            queries = [f'{kw} {random.choice(config["role_words"])} {config.get("search_suffix", "")}'.strip() for kw in final_keywords]
            random.shuffle(queries)
            progress_text = st.empty()
            
            with st.spinner("深挖中，正在进行灵活的 B2B 属性验证..."):
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
                            
                            if any(x in text for x in CHINA_GEO_BLOCKLIST + STRICT_BUSINESS_BLOCKLIST + IRRELEVANT_INDUSTRIES_BLOCKLIST): continue
                            if not any(b2b_kw in text for b2b_kw in B2B_REQUIRED_KEYWORDS): continue
                                
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
                st.success(f"🎉 成功筛选并斩获 {len(scored_leads)} 家全新优质 B2B 经销商！")
            else: st.warning("未发现符合 B2B 标准的新线索，请尝试更换产品线或重试。")

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
            
            # 这里增加了状态的展示
            st.markdown(f"**官网**: [{lead['官网']}]({lead['官网']}) | **核心匹配产品**: `{lead['匹配产品']}` | **当前状态**: `{lead.get('状态', '未联系')}`")
            
            history_count = len(emails_df[emails_df['收件人'] == lead['邮箱']]) if not emails_df.empty and lead['邮箱'] else 0
            
            if lead['官网'] not in st.session_state.local_reports:
                if st.button(f"📊 生成深调档案 (官网+社媒提取)", key=f"bg_{i}"):
                    st.session_state.local_reports[lead['官网']] = local_background_check(lead, lead['国家'])
                    st.rerun()
            if lead['官网'] in st.session_state.local_reports:
                with st.expander("✅ 展开查看：背景调查报告", expanded=False): st.markdown(st.session_state.local_reports[lead['官网']])
            
            with st.expander("✉️ 展开开发信工作台 (撰写与发送)", expanded=True):
                lang = "es" if "Mexico" in lead['国家'] or "西班牙" in lead['国家'] else "en"
                c_ang, c_to = st.columns([2, 1])
                with c_ang: angle = st.selectbox("1️⃣ 选择霸气外贸开发策略", list(EMAIL_TEMPLATES[lang].keys()), index=0, key=f"ang_{i}")
                with c_to: target_email = st.text_input("收件人", value=lead['邮箱'], key=f"to_{i}")
                
                tpl = EMAIL_TEMPLATES[lang][angle].split("\n\n", 1)
                mail_sub = st.text_input("邮件主题", value=tpl[0].replace("Subject: ", "").replace("Asunto: ", "").format(company_name=lead['公司名'], core_product=lead['匹配产品']), key=f"sub_{i}_{angle}")
                mail_body = st.text_area("邮件正文 (可自由修改)", value=tpl[1].format(company_name=lead['公司名'], core_product=lead['匹配产品']), height=280, key=f"body_{i}_{angle}")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("🚀 立即 SMTP 发送", key=f"snd_{i}", type="primary"):
                        success, msg = send_smtp_email(target_email, mail_sub, mail_body)
                        if success:
                            st.success("✅ 邮件发送成功！状态已自动更新为[已联系]")
                            db.log_email({"邮件ID": f"MAIL_{int(time.time())}", "客户公司": lead['公司名'], "收件人": target_email, "发送时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "主题": mail_sub, "内容摘要": "...", "状态": "成功"})
                            db.update_client_status(lead['客户ID'], "已联系") # 【修复2】更新数据库状态
                            lead['状态'] = "已联系" # 更新当前页面缓存状态
                            st.rerun()
                        else: st.error(msg)
            st.markdown("---")

elif page == "🗃️ 客户 CRM 数据库":
    st.title("🗃️ 客户管理中心")
    df = db.get_clients()
    
    if not df.empty:
        # =========================================================
        # 第一步一键快捷清理台（秒杀旧数据）
        # =========================================================
        st.markdown("### 🗑️ 快捷清理台 (第一步直接删除)")
        st.caption("注：删除后该客户将被加入【永久黑名单】，后续挖掘永不出现！")
        
        c_sel, c_btn = st.columns([4, 1])
        with c_sel:
            client_options = [f"{row['公司名']} | {row['匹配产品']} ({row['客户ID']})" for _, row in df.iterrows()]
            selected_to_delete = st.selectbox("👇 选择你要清理的无效客户：", client_options)
            
        with c_btn:
            st.write("") 
            st.write("")
            if st.button("🚨 一键彻底拉黑删除", type="primary", use_container_width=True):
                if selected_to_delete:
                    ext_id = selected_to_delete.split("(")[-1].replace(")", "")
                    db.delete_client(ext_id)
                    st.success("删除成功并已加入防重复黑名单！正在刷新...")
                    time.sleep(0.5)
                    st.rerun()
        st.markdown("---")
        
        # =========================================================
        # 下方保留：客户查询与二次发件工作台
        # =========================================================
        st.info("💡 搜索框输入公司名，可唤醒该客户的【专属开发信发送台】。")
        search = st.text_input("🔍 搜索公司名进行二次跟进 (支持模糊搜索)")
        
        if search: df_filtered = df[df['公司名'].str.contains(search, case=False, na=False)]
        else: df_filtered = df
            
        st.dataframe(df_filtered, use_container_width=True)

        if search and not df_filtered.empty:
            st.markdown("---")
            st.subheader("🚀 客户专属跟进台")
            emails_df = db.get_emails()
            
            for i, row in df_filtered.iterrows():
                lead = {k: ("" if pd.isna(v) else v) for k, v in row.to_dict().items()}
                st.markdown(f"#### 🎯 {lead.get('公司名', '未知公司')}")
                st.markdown(f"**官网**: {lead.get('官网', '')} | **主营标签**: `{lead.get('匹配产品', 'B2B Auto Tools')}` | **状态**: `{lead.get('状态', '未联系')}`")

                history_count = len(emails_df[emails_df['收件人'] == lead.get('邮箱')]) if not emails_df.empty and lead.get('邮箱') else 0

                with st.expander("✉️ 唤醒开发信发送台", expanded=True):
                    lang = "es" if "Mexico" in str(lead.get('国家','')) or "西班牙" in str(lead.get('国家','')) else "en"
                    c_ang, c_to = st.columns([2, 1])
                    with c_ang: angle = st.selectbox("1️⃣ 选择霸气外贸开发策略", list(EMAIL_TEMPLATES[lang].keys()), index=0, key=f"crm_ang_{i}")
                    with c_to: target_email = st.text_input("收件人 (可自由修改替换)", value=str(lead.get('邮箱', '')), key=f"crm_to_{i}")
                    
                    tpl = EMAIL_TEMPLATES[lang][angle].split("\n\n", 1)
                    sub_fmt = tpl[0].replace("Subject: ", "").replace("Asunto: ", "").format(company_name=lead.get('公司名',''), core_product=lead.get('匹配产品','Auto Tools'))
                    body_fmt = tpl[1].format(company_name=lead.get('公司名',''), core_product=lead.get('匹配产品','Auto Tools'))
                    
                    mail_sub = st.text_input("邮件主题", value=sub_fmt, key=f"crm_sub_{i}_{angle}")
                    mail_body = st.text_area("邮件正文", value=body_fmt, height=280, key=f"crm_body_{i}_{angle}")
                    
                    if st.button("🚀 立即 SMTP 发送", key=f"crm_snd_{i}", type="primary"):
                        if not target_email.strip():
                            st.error("⚠️ 邮箱不能为空！请手动输入。")
                        else:
                            success, msg = send_smtp_email(target_email, mail_sub, mail_body)
                            if success:
                                st.success("✅ 邮件发送成功！客户状态已全自动更新为[已联系]")
                                db.log_email({"邮件ID": f"MAIL_{int(time.time())}", "客户公司": lead.get('公司名',''), "收件人": target_email, "发送时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "主题": mail_sub, "内容摘要": "...", "状态": "成功"})
                                db.update_client_status(lead.get('客户ID'), "已联系") # 【修复2】更新数据库状态
                                st.rerun()
                            else: st.error(msg)
            st.markdown("---")
            
    else: st.info("数据库目前为空，请去工作台挖掘客户。")

elif page == "📨 发送追踪记录":
    st.title("📨 邮件发送追踪")
    df_logs = db.get_emails()
    if not df_logs.empty:
        st.dataframe(df_logs.sort_values(by="发送时间", ascending=False), use_container_width=True)
        st.download_button("📥 导出发送报告", df_logs.to_csv(index=False).encode('utf-8-sig'), "Email_Logs.csv", "text/csv")
    else: st.info("暂无发信记录。")
