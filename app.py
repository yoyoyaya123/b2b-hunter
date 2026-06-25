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

# ==================== 数据库引擎 (修复了CSV解析崩溃与脏数据污染) ====================
class DatabaseManager:
    def __init__(self):
        self.use_gsheets = False
        self.client = None
        self.sheet = None
        self.client_cols = ["客户ID", "公司名", "官网", "邮箱", "联系方式", "匹配产品", "国家", "状态", "添加时间"]
        self.email_cols = ["邮件ID", "客户公司", "收件人", "发送时间", "主题", "内容摘要", "状态"]
        self._init_connection()

    def _init_connection(self):
        if "gcp_service_account" in st.secrets and "gsheets_url" in st.secrets:
            try:
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
                self.client = gspread.authorize(creds)
                self.sheet = self.client.open_by_url(st.secrets["gsheets_url"])
                self.use_gsheets = True
            except Exception:
                pass
        
        # 初始化本地文件，如果不存在则创建
        if not os.path.exists("db_clients.csv"):
            pd.DataFrame(columns=self.client_cols).to_csv("db_clients.csv", index=False)
        if not os.path.exists("db_emails.csv"):
            pd.DataFrame(columns=self.email_cols).to_csv("db_emails.csv", index=False)

    def get_clients(self):
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Clients")
                return pd.DataFrame(worksheet.get_all_records())
            except: pass
        
        # 增加容错自愈：如果 CSV 损坏，直接重置，防止页面崩溃
        try:
            return pd.read_csv("db_clients.csv")
        except Exception:
            df = pd.DataFrame(columns=self.client_cols)
            df.to_csv("db_clients.csv", index=False)
            return df

    def add_client(self, client_data):
        # 强制清洗：只取规定的列，抛弃 HTML源码 等会破坏 CSV 格式的字段
        clean_data = {k: client_data.get(k, "") for k in self.client_cols}
        df = pd.DataFrame([clean_data])
        
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Clients")
                worksheet.append_row(list(clean_data.values()))
                return
            except: pass
            
        df.to_csv("db_clients.csv", mode='a', header=False, index=False)

    def get_emails(self):
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Emails")
                return pd.DataFrame(worksheet.get_all_records())
            except: pass
            
        try:
            return pd.read_csv("db_emails.csv")
        except Exception:
            df = pd.DataFrame(columns=self.email_cols)
            df.to_csv("db_emails.csv", index=False)
            return df

    def log_email(self, email_data):
        clean_data = {k: email_data.get(k, "") for k in self.email_cols}
        df = pd.DataFrame([clean_data])
        
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Emails")
                worksheet.append_row(list(clean_data.values()))
                return
            except: pass
            
        df.to_csv("db_emails.csv", mode='a', header=False, index=False)

db = DatabaseManager()

# ==================== 本地缓存 (保障分页与状态) ====================
if 'all_leads' not in st.session_state:
    st.session_state.all_leads = []
    st.session_state.excluded_domains = set()
    st.session_state.local_reports = {}
    st.session_state.current_page = 0

# ==================== 核心过滤黑名单与产品库 ====================
PLATFORM_BLOCKLIST = [
    "iqsdirectory.", "directory.", "yellowpages.", "thomasnet.", "kompass.", "europages.", 
    "yelp.", "zoominfo.", "dnb.", "manta.", "crunchbase.", "trade.", "b2b.", "globalsources.", 
    "made-in-china.", "alibaba.", "aliexpress.", "indiamart.", "tradekey.", "hktdc.", "manufacturers.", "suppliers.",
    "amazon.", "ebay.", "walmart.", "shopee.", "lazada.", "etsy.", "wayfair.", "temu.", "shein.", "trustpilot.",
    "autozone.", "oreillyauto.", "napaonline.", "advanceautoparts.", "halfords.", "grainger.", "fastenal.", 
    "mscdirect.", "homedepot.", "lowes.", "menards.", "target.", "costco.", "carrefour.", "aldi.", "tesco.", 
    "macys.", "snap-on.", "mactools.", "matcotools.", "harborfreight.", "shopping.", "prices.", "vevor.", 
    "northerntool.", "princessauto.", "kmstools.", "machineryhouse.", "news.", "blog.", "magazine.", "journal.", 
    "press.", "wiki.", "forbes.", "reuters.", "bloomberg.", ".cn", ".com.cn", ".tw", ".hk"
]
TITLE_BLOCKLIST = ["directory", "top 10", "top 20", "top 5", "list of", "manufacturers in", "suppliers of", "best suppliers", "news", "blog", "magazine", "press release", "yellow pages", "b2b platform"]
CHINA_GEO_BLOCKLIST = ["guangdong", "shenzhen", "guangzhou", "dongguan", "foshan", "zhongshan", "zhuhai", "zhejiang", "ningbo", "hangzhou", "yiwu", "wenzhou", "taizhou", "jinhua", "shaoxing", "jiangsu", "shanghai", "shandong", "qingdao", "jinan", "hebei", "henan", "beijing", "tianjin", "+86 ", "0086", "86-1", "86-0", "made in china", "china mainland", "mainland china", "chinese supplier"]
STRICT_BUSINESS_BLOCKLIST = ["investor relations", "stock symbol", "shareholders", "annual report", "subsidiary of", "listed company", "nasdaq", "nyse", "group of companies", "retail store", "consumer electronics", "superstore", "hypermarket", "retail only", "auto repair shop", "repair service", "body shop", "car wash", "tyre shop", "tire shop", "mechanic service", "mobile mechanic", "towing service", "collision center", "auto care clinic", "taller mecánico", "centro de reparación", "chapa y pintura", "grúa", "автосервис", "ремонт авто", "шиномонтаж", "СТО", "Autoreparatur", "Reparaturservice", "Reifenservice", "Abschleppdienst"]
IRRELEVANT_INDUSTRIES_BLOCKLIST = ["garden tools", "lawn mower", "woodworking tools", "plumbing tools", "construction equipment", "agricultural machinery", "industrial supplies"]

BASE_EN_PRODUCTS = {"01 仪表检测工具": {"search": ["radiator pressure tester", "cylinder compression tester", "fuel pressure gauge"]}, "02 液体更换/补充工具": {"search": ["brake fluid replacement tool", "brake bleeder", "oil extractor"]}, "03 汽车空调制冷工具": {"search": ["a/c manifold gauge", "refrigerant charging kit", "a/c leak detection"]}, "04 车身拆卸/卡扣工具": {"search": ["trim removal tool", "plastic pry tools", "car clip set"]}, "05 发动机正时工具": {"search": ["engine timing tool", "camshaft locking tool", "crankshaft tool"]}}
BASE_ES_PRODUCTS = {"01 仪表检测工具": {"search": ["probador de presión de radiador", "comprobador de compresión", "medidor de presión de combustible"]}, "02 液体更换/补充工具": {"search": ["purgador de frenos", "extractor de aceite", "bomba de vacío"]}, "03 汽车空调制冷工具": {"search": ["manómetro de aire acondicionado", "kit de carga de refrigerante", "detector de fugas a/c"]}, "04 车身拆卸/卡扣工具": {"search": ["herramientas para desmontar molduras", "alicates para abrazaderas", "kit de grapas coche"]}, "05 发动机正时工具": {"search": ["kit de calado de motor", "herramienta de sincronización", "bloqueo de árbol de levas"]}}

COUNTRY_CONFIG = {
    "🇺🇸 美国 (USA)": {"region": "us-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇬🇧 英国 (UK)": {"region": "uk-en", "role_words": ["wholesaler", "distributor", "supplier", "dealer"], "product_lines": BASE_EN_PRODUCTS},
    "🇲🇽 墨西哥 (Mexico)": {"region": "mx-es", "role_words": ["mayorista", "distribuidor", "importador", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
    "🇦🇪 中东地区 (UAE/沙特)": {"region": "ae-en", "search_suffix": "UAE OR Saudi Arabia OR Dubai", "role_words": ["wholesaler", "distributor", "importer", "equipment supplier"], "product_lines": BASE_EN_PRODUCTS},
    "🇩🇪 德国 (Germany)": {"region": "de-de", "role_words": ["Großhandel", "Importeur", "Distributor", "Händler"], "product_lines": {"01 仪表检测": {"search": ["Kühlsystem-Dichtheitsprüfer", "Kompressionstester"]}}},
    "🇪🇸 西班牙/南美大区": {"region": "es-es", "role_words": ["mayorista", "importador", "distribuidor", "proveedor"], "product_lines": BASE_ES_PRODUCTS},
}

EMAIL_TEMPLATES = {
    "en": {
        "供应链降本切入 (Cost & Margin)": "Subject: Supply chain idea for {company_name}\n\nHi team at {company_name},\n\nI noticed you supply {core_product} and related tools to the local market.\n\nWith recent supply chain shifts, many independent distributors are facing margin squeezes from local middlemen. We help suppliers like you bypass the middleman and source directly, allowing for smaller, flexible trial orders without tying up your cash flow.\n\nWould you be open to a quick chat to see if this fits your upcoming inventory planning?\n\nBest regards,\n[Your Name]",
        "测试试单切入 (Trial Order)": "Subject: Trial order support for {core_product}\n\nHi team at {company_name},\n\nI see you focus on {core_product} for the local auto repair market.\n\nTesting a new supplier can be risky. To help you lower the trial cost, we offer small MOQ test orders and pre-shipment video confirmations, ensuring you get exactly what your clients need without heavy upfront investment.\n\nAre you open to exploring a risk-free trial order this quarter?\n\nBest regards,\n[Your Name]"
    },
    "es": {
        "供应链降本切入 (Cost & Margin)": "Asunto: Idea de suministro para {company_name}\n\nHola equipo de {company_name},\n\nNoté que distribuyen {core_product} en su mercado local.\n\nMuchos distribuidores independientes enfrentan márgenes reducidos por los intermediarios. Ayudamos a importadores como ustedes a comprar directamente desde el origen, permitiendo pedidos de prueba pequeños y flexibles sin comprometer su flujo de caja.\n\n¿Estarían abiertos a una breve charla para ver si esto encaja en su planificación de inventario?\n\nSaludos cordiales,\n[Tu Nombre]",
        "测试试单切入 (Trial Order)": "Asunto: Soporte de pedidos de prueba para {core_product}\n\nHola equipo de {company_name},\n\nVeo que se enfocan en {core_product}.\n\nProbar un nuevo proveedor puede ser riesgoso. Para reducir el costo de prueba, ofrecemos pequeños pedidos y confirmaciones por video antes del envío, asegurando que obtengan lo que necesitan sin una gran inversión inicial.\n\n¿Están abiertos a explorar un pedido de prueba sin riesgos este trimestre?\n\nSaludos cordiales,\n[Tu Nombre]"
    }
}

# ==================== 发信引擎 ====================
def send_smtp_email(to_addr, subject, body):
    if not st.session_state.get('smtp_user') or not st.session_state.get('smtp_pass'):
        return False, "⚠️ 错误: 请先在左侧边栏配置并保存 SMTP 邮箱账号和授权码！"
    try:
        msg = MIMEMultipart()
        msg['From'] = st.session_state['smtp_user']
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(body + st.session_state.get('email_sign', ''), 'plain', 'utf-8'))
        
        server = smtplib.SMTP(st.session_state['smtp_server'], st.session_state['smtp_port'])
        server.starttls()
        server.login(st.session_state['smtp_user'], st.session_state['smtp_pass'])
        server.send_message(msg)
        server.quit()
        return True, "发送成功"
    except Exception as e:
        return False, f"发送失败: {str(e)}"

# ==================== 侧边栏导航与配置 ====================
with st.sidebar:
    st.header("🧭 系统导航")
    page = st.radio("请选择功能模块:", ["🔍 获客与开发工作台", "🗃️ 客户 CRM 数据库", "📨 发送追踪记录"])
    
    st.markdown("---")
    with st.expander("⚙️ 邮箱 SMTP 配置 (用于自动发信)", expanded=False):
        smtp_server = st.text_input("SMTP 服务器 (如 smtp.gmail.com)", value=st.session_state.get('smtp_server', 'smtp.gmail.com'))
        smtp_port = st.number_input("端口号", value=st.session_state.get('smtp_port', 587))
        smtp_user = st.text_input("你的邮箱账号", value=st.session_state.get('smtp_user', ''))
        smtp_pass = st.text_input("邮箱授权码 (非登录密码)", type="password", value=st.session_state.get('smtp_pass', ''))
        email_sign = st.text_area("邮件签名", value=st.session_state.get('email_sign', '\n\nBest regards,\nSales Team'))
        if st.button("💾 保存发信配置"):
            st.session_state.update({'smtp_server': smtp_server, 'smtp_port': smtp_port, 'smtp_user': smtp_user, 'smtp_pass': smtp_pass, 'email_sign': email_sign})
            st.success("配置已保存")

    if page == "🔍 获客与开发工作台":
        st.markdown("---")
        st.header("🌍 深度搜索配置")
        country_options = list(COUNTRY_CONFIG.keys()) + ["🌍 + 自定义其他国家 (自由配置)"]
        selected_country = st.selectbox("🎯 选择目标国家", country_options)

        custom_name, custom_roles_list, custom_excludes_list = "", [], []
        
        if selected_country == "🌍 + 自定义其他国家 (自由配置)":
            st.info("💡 **上帝模式**：您现在可以搜索全球任何角落！")
            custom_name = st.text_input("1. 目标国家英文名 (如: Australia)", value="Australia")
            custom_roles = st.text_input("2. 经销商词汇", value="wholesaler, distributor, importer, supplier")
            custom_excludes = st.text_input("3. 额外排除词汇", value="repair service, mechanic, car wash")
            custom_roles_list = [x.strip() for x in custom_roles.split(",")]
            custom_excludes_list = [x.strip() for x in custom_excludes.split(",")]
            config = {"region": "wt-wt", "search_suffix": custom_name, "role_words": custom_roles_list, "product_lines": BASE_EN_PRODUCTS}
            display_country_name = custom_name
        else:
            config = COUNTRY_CONFIG[selected_country]
            display_country_name = selected_country

        st.subheader("📦 选择侦测产品线")
        selected_lines = [line for line in config['product_lines'].keys() if st.checkbox(line, value=True)]
        
        manual_keywords = st.text_area("🔧 补充小语种产品词汇 (可选)", height=80)
        final_keywords = []
        for line in selected_lines:
            final_keywords.extend(config['product_lines'][line]['search'])
        if manual_keywords.strip():
            final_keywords.extend([k.strip() for k in manual_keywords.splitlines() if k.strip()])
        final_keywords = list(set(final_keywords))

# ==================== 页面 1: 获客与工作台 ====================
def duckduckgo_search(query, region, max_results=20):
    queries_to_try = [f'{query} -amazon -aliexpress -vevor', query]
    for q in queries_to_try:
        for backend in ['lite', 'html', 'api']:
            try:
                results = []
                with DDGS() as ddgs:
                    for r in ddgs.text(q, region=region, backend=backend, max_results=max_results):
                        results.append(r['href'])
                if results: return results
            except: continue
    return []

def local_background_check(lead, country):
    soup = BeautifulSoup(lead['HTML内容'], 'html.parser')
    fb_links = list(set(re.findall(r'(https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+)', lead['HTML内容'])))
    social_str = f"Facebook: {fb_links[0]}" if fb_links else "未提取到社媒，建议手动检索。"
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    intro = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else f"系统分析：该公司为 {country} 本地独立分销商。"
    
    return f"""
### 📊 资深业务员：{lead['公司名']} 客户背景深度调研报告
**1. 官方网站**：{lead['官网']}
**2. 公司介绍**：{intro[:300]}...
**3. 社交媒体与门店**：{social_str}
**4. 员工联系与职位**：📥 发现邮箱：`{lead['邮箱']}`
**5. 核心痛点推演**：① 供应链成本倒挂 ② 起订量不灵活 ③ 售后合规风险。
**6. 商业模式**：经典的 **B2B 区域进口分销 + 独立站直营**。
"""

if page == "🔍 获客与开发工作台":
    st.title("🔧 获客与开发工作台 (全能深度版)")
    st.markdown("🎯 **系统特色**: 原汁原味的【国家/产品组合搜索】回归！融合 14维度背调与自动化发信系统！")

    if st.button(f"🔍 强力深挖 5 家 【{display_country_name}】 顶级经销商", type="primary"):
        if not final_keywords:
            st.error("请先在左侧边栏选择产品线或输入关键词！")
        else:
            scored_leads = []
            seen = st.session_state.excluded_domains.copy()
            queries = []
            search_suffix = config.get("search_suffix", "")
            for kw in final_keywords:
                role = random.choice(config["role_words"])
                queries.append(f'{kw} {role} {search_suffix}'.strip())
            random.shuffle(queries)

            progress_text = st.empty()
            with st.spinner("系统发射深海探测器... 正无情粉碎所有上市集团、黄页、Vevor和修理厂..."):
                for q in queries:
                    if len(scored_leads) >= 5: break
                    progress_text.write(f"🔄 正在深挖: `{q}` (已验证合规 {len(scored_leads)}/5 家)...")
                    urls = duckduckgo_search(q, region=config.get("region", "wt-wt"), max_results=15)
                    if not urls: time.sleep(2); continue
                    
                    for url in urls:
                        if len(scored_leads) >= 5: break
                        domain = urlparse(url).netloc.lower()
                        if any(b in domain for b in PLATFORM_BLOCKLIST): continue
                        if domain in seen: continue
                        
                        try:
                            html = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'}).text
                            soup = BeautifulSoup(html, 'html.parser')
                            text = soup.get_text().lower()
                            
                            if any(x in text for x in CHINA_GEO_BLOCKLIST + STRICT_BUSINESS_BLOCKLIST): continue
                            matched = [kw for kw in final_keywords if kw.lower() in text]
                            if not matched: continue
                            
                            comp_name = soup.title.string.strip() if soup.title else domain
                            emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
                            
                            lead_data = {
                                "客户ID": f"CUS_{int(time.time())}_{random.randint(100,999)}",
                                "公司名": comp_name[:60],
                                "官网": url,
                                "邮箱": emails[0] if emails else "",
                                "联系方式": " | ".join(emails[:2]) if emails else "表单",
                                "匹配产品": matched[0],
                                "国家": display_country_name,
                                "状态": "未联系",
                                "添加时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "HTML内容": html,
                                "产品数": len(matched)
                            }
                            scored_leads.append(lead_data)
                            seen.add(domain)
                        except: pass
                    time.sleep(1)
            
            progress_text.empty()
            if scored_leads:
                st.session_state.all_leads.extend(scored_leads)
                st.session_state.excluded_domains = seen
                st.session_state.current_page = (len(st.session_state.all_leads) - 1) // 5
                for l in scored_leads: db.add_client(l) # 同步写入 CRM 库，现已过滤 HTML 等乱码字段
                st.success(f"🎉 斩获成功！精准验证 {len(scored_leads)} 家合规经销商，已存入 CRM 数据库！")
            else:
                st.warning("过滤条件极其严苛，本次搜寻被全量拦截。请重新点击或放宽搜索范围！")

    # ===== 结果渲染区域 =====
    if st.session_state.all_leads:
        total_leads = len(st.session_state.all_leads)
        total_pages = (total_leads - 1) // 5 + 1
        current_page = st.session_state.current_page

        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("⬅️ 上一页", disabled=(current_page == 0)):
                st.session_state.current_page -= 1; st.rerun()
        with col2:
            if st.button("下一页 ➡️", disabled=(current_page >= total_pages - 1)):
                st.session_state.current_page += 1; st.rerun()
        with col3:
            st.write(f"第 {current_page+1}/{total_pages} 页 · 共 {total_leads} 家客户")

        start_idx = current_page * 5
        end_idx = min(start_idx + 5, total_leads)
        
        for i in range(start_idx, end_idx):
            lead = st.session_state.all_leads[i]
            lead_url = lead['官网']
            
            st.subheader(f"{i+1}. {lead['公司名']}")
            st.markdown(f"**官网**: [{lead_url}]({lead_url}) | **匹配产品**: `{lead['匹配产品']}`")
            
            if lead_url not in st.session_state.local_reports:
                if st.button(f"📊 生成 14维度背调档案", key=f"bg_btn_{i}"):
                    st.session_state.local_reports[lead_url] = local_background_check(lead, lead['国家'])
                    st.rerun()
            
            if lead_url in st.session_state.local_reports:
                with st.expander("✅ 展开查看：14维度背景调查报告", expanded=False):
                    st.markdown(st.session_state.local_reports[lead_url])
            
            with st.expander("✉️ 展开开发信工作台 (撰写与发送)", expanded=True):
                lang = "es" if "Mexico" in lead['国家'] or "西班牙" in lead['国家'] else "en"
                
                col_angle, col_to = st.columns([2, 1])
                with col_angle:
                    angle = st.selectbox("1️⃣ 选择开发切入角度模板", list(EMAIL_TEMPLATES[lang].keys()), key=f"angle_{i}")
                with col_to:
                    target_email = st.text_input("收件人", value=lead['邮箱'], key=f"to_{i}")
                
                tpl = EMAIL_TEMPLATES[lang][angle]
                raw_body = tpl.split("\n\n", 1)
                default_sub = raw_body[0].replace("Subject: ", "").replace("Asunto: ", "").format(company_name=lead['公司名'], core_product=lead['匹配产品'])
                default_body = raw_body[1].format(company_name=lead['公司名'], core_product=lead['匹配产品'])
                
                mail_sub = st.text_input("邮件主题", value=default_sub, key=f"sub_{i}")
                mail_body = st.text_area("邮件正文 (可自由修改)", value=default_body, height=200, key=f"body_{i}")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("🚀 立即 SMTP 发送", key=f"send_{i}", type="primary"):
                        if not target_email: st.error("请输入收件人邮箱")
                        else:
                            with st.spinner("发送中..."):
                                success, msg = send_smtp_email(target_email, mail_sub, mail_body)
                                if success:
                                    st.success("✅ 邮件发送成功！")
                                    db.log_email({"邮件ID": f"MAIL_{int(time.time())}", "客户公司": lead['公司名'], "收件人": target_email, "发送时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "主题": mail_sub, "内容摘要": mail_body[:50]+"...", "状态": "成功"})
                                else: st.error(msg)
                with c2:
                    st.code(f"Subject: {mail_sub}\n\n{mail_body}", language="text")
                with c3:
                    if st.button("🔖 仅标记为已手动发送", key=f"mark_{i}"):
                        db.log_email({"邮件ID": f"MAIL_{int(time.time())}", "客户公司": lead['公司名'], "收件人": target_email, "发送时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "主题": mail_sub, "内容摘要": "(手动复制发送)", "状态": "手动标记"})
                        st.success("已记录到 CRM 追踪历史！")
            st.markdown("---")

# ==================== 页面 2: 客户 CRM 数据库 ====================
elif page == "🗃️ 客户 CRM 数据库":
    st.title("🗃️ 客户中心 (Clients Database)")
    df = db.get_clients()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("🔍 搜索公司名或国家")
    
    if not df.empty:
        if search_term:
            df = df[df['公司名'].str.contains(search_term, case=False) | df['国家'].str.contains(search_term, case=False)]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("数据库目前为空，请先前往获客工作台抓取。")

    with st.expander("➕ 手动录入新客户"):
        with st.form("add_client_form"):
            c_name = st.text_input("公司名")
            c_url = st.text_input("官网")
            c_email = st.text_input("邮箱")
            c_prod = st.text_input("意向产品")
            submitted = st.form_submit_button("录入数据库")
            if submitted and c_name:
                db.add_client({"客户ID": f"MAN_{int(time.time())}", "公司名": c_name, "官网": c_url, "邮箱": c_email, "联系方式": c_email, "匹配产品": c_prod, "国家": "手动录入", "状态": "未联系", "添加时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})
                st.success("录入成功！")

# ==================== 页面 3: 发送追踪记录 ====================
elif page == "📨 发送追踪记录":
    st.title("📨 邮件发送追踪 (Email Logs)")
    df_logs = db.get_emails()
    
    if not df_logs.empty:
        st.dataframe(df_logs, use_container_width=True)
        csv = df_logs.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 导出发送记录为 CSV", data=csv, file_name="JYTOOL_Email_Logs.csv", mime="text/csv")
    else:
        st.info("暂无发送记录，您发送或标记的邮件将显示在这里。")
