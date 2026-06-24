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

st.set_page_config(page_title="JYTOOL 全球 B2B 自动化获客 CRM", layout="wide")

# ==================== 数据库引擎 (Google Sheets / 本地回退) ====================
# 如果没有配置 Google 密钥，系统会自动降级使用本地 CSV，保证程序不崩溃
class DatabaseManager:
    def __init__(self):
        self.use_gsheets = False
        self.client = None
        self.sheet = None
        self._init_connection()

    def _init_connection(self):
        if "gcp_service_account" in st.secrets and "gsheets_url" in st.secrets:
            try:
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
                self.client = gspread.authorize(creds)
                self.sheet = self.client.open_by_url(st.secrets["gsheets_url"])
                self.use_gsheets = True
            except Exception as e:
                st.sidebar.error(f"Google Sheets 连接失败: {e}")
        
        # 确保本地数据文件存在
        if not os.path.exists("db_clients.csv"):
            pd.DataFrame(columns=["客户ID", "公司名", "官网", "邮箱", "联系方式", "匹配产品", "国家", "状态", "添加时间"]).to_csv("db_clients.csv", index=False)
        if not os.path.exists("db_emails.csv"):
            pd.DataFrame(columns=["邮件ID", "客户公司", "收件人", "发送时间", "主题", "内容摘要", "状态"]).to_csv("db_emails.csv", index=False)

    def get_clients(self):
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Clients")
                return pd.DataFrame(worksheet.get_all_records())
            except: pass
        return pd.read_csv("db_clients.csv")

    def add_client(self, client_data):
        df = pd.DataFrame([client_data])
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Clients")
                worksheet.append_row(list(client_data.values()))
                return
            except: pass
        df.to_csv("db_clients.csv", mode='a', header=False, index=False)

    def get_emails(self):
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Emails")
                return pd.DataFrame(worksheet.get_all_records())
            except: pass
        return pd.read_csv("db_emails.csv")

    def log_email(self, email_data):
        df = pd.DataFrame([email_data])
        if self.use_gsheets:
            try:
                worksheet = self.sheet.worksheet("Emails")
                worksheet.append_row(list(email_data.values()))
                return
            except: pass
        df.to_csv("db_emails.csv", mode='a', header=False, index=False)

db = DatabaseManager()

# ==================== 侧边栏：多页面导航与配置 ====================
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
        
        if st.button("💾 保存配置"):
            st.session_state.update({'smtp_server': smtp_server, 'smtp_port': smtp_port, 'smtp_user': smtp_user, 'smtp_pass': smtp_pass, 'email_sign': email_sign})
            st.success("SMTP配置已保存(仅当前会话有效)")

    if not db.use_gsheets:
        st.warning("⚠️ 当前未连接 Google Sheets，数据暂存于云端临时区 (重启可能会丢失)。请查阅说明配置 GSheets。")

# ==================== 底层数据与规则库 ====================
PLATFORM_BLOCKLIST = ["directory.", "yellowpages.", "alibaba.", "amazon.", "ebay.", "aliexpress.", "vevor.", "news.", "blog."]
CHINA_GEO_BLOCKLIST = ["guangdong", "shenzhen", "zhejiang", "ningbo", "china mainland"]
STRICT_BUSINESS_BLOCKLIST = ["investor relations", "repair shop", "car wash", "taller mecánico", "автосервис"]
BASE_EN_PRODUCTS = {"汽保工具": {"search": ["radiator pressure tester", "cylinder compression tester", "brake bleeder", "oil extractor", "a/c manifold gauge"]}}

EMAIL_TEMPLATES = {
    "en": {
        "Cost & Margin": {"sub": "Supply chain idea for {company}", "body": "Hi team at {company},\n\nI noticed you supply {product} to the local market.\n\nWith recent supply chain shifts, many independent distributors are facing margin squeezes. We help suppliers bypass the middleman and source directly, allowing for flexible trial orders.\n\nWould you be open to a quick chat?"},
        "Trial Order": {"sub": "Trial order support for {product}", "body": "Hi team at {company},\n\nTesting a new supplier can be risky. To help you lower the trial cost for {product}, we offer small MOQ test orders and pre-shipment video confirmations.\n\nAre you open to exploring a risk-free trial order this quarter?"}
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

# ==================== 抓取逻辑 ====================
def search_and_score(query, target_num=3):
    try:
        urls = []
        with DDGS() as ddgs:
            for r in ddgs.text(f'{query} -amazon -aliexpress -vevor', max_results=15):
                urls.append(r['href'])
        
        results = []
        for url in urls:
            if len(results) >= target_num: break
            domain = urlparse(url).netloc.lower()
            if any(b in domain for b in PLATFORM_BLOCKLIST): continue
            try:
                html = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'}).text
                text = BeautifulSoup(html, 'html.parser').get_text().lower()
                
                # 提取联系方式
                emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))
                # 简单拦截
                if any(x in text for x in CHINA_GEO_BLOCKLIST + STRICT_BUSINESS_BLOCKLIST): continue
                
                matched = [kw for kw in BASE_EN_PRODUCTS["汽保工具"]["search"] if kw.lower() in text]
                if not matched: continue
                
                comp_name = BeautifulSoup(html, 'html.parser').title.string.strip() if BeautifulSoup(html, 'html.parser').title else domain
                
                results.append({
                    "客户ID": f"CUS_{int(time.time())}_{random.randint(100,999)}",
                    "公司名": comp_name[:40],
                    "官网": url,
                    "邮箱": emails[0] if emails else "",
                    "联系方式": " | ".join(emails[:2]),
                    "匹配产品": matched[0],
                    "国家": "自动识别",
                    "状态": "未联系",
                    "添加时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                })
            except: continue
        return results
    except: return []

# ==================== 页面 1: 获客与开发工作台 ====================
if page == "🔍 获客与开发工作台":
    st.title("🚀 实时获客与自动化营销工作台")
    query = st.text_input("输入精准指令 (如: radiator tester distributor Australia)")
    
    if st.button("开始深挖探测", type="primary"):
        with st.spinner("系统正在全网检索并验证..."):
            leads = search_and_score(query)
            if leads:
                st.session_state['current_leads'] = leads
                for l in leads: db.add_client(l) # 自动入库
                st.success(f"斩获 {len(leads)} 家合规客户，已自动存入 CRM 数据库！")
            else:
                st.warning("未找到匹配客户，请更换关键词。")

    if 'current_leads' in st.session_state:
        st.markdown("---")
        for i, lead in enumerate(st.session_state['current_leads']):
            st.subheader(f"{i+1}. {lead['公司名']}")
            st.markdown(f"**🌐 官网**: [{lead['官网']}]({lead['官网']})")
            
            # A) 匹配产品展示区
            st.info(f"🎯 **系统诊断 (为何推荐)**: 探测到该独立站源码及前端页面深度包含汽车专用工具 `[{lead['匹配产品']}]`，符合对口 B2B 采购商特征。")
            
            # B) 开发信编辑区
            with st.expander("✉️ 展开开发信工作台 (撰写与发送)", expanded=True):
                col_sub, col_to = st.columns([3, 1])
                tpl = EMAIL_TEMPLATES["en"]["Cost & Margin"]
                
                with col_to:
                    target_email = st.text_input("收件人", value=lead['邮箱'], key=f"to_{i}")
                with col_sub:
                    mail_sub = st.text_input("邮件主题", value=tpl["sub"].format(company=lead['公司名']), key=f"sub_{i}")
                
                mail_body = st.text_area("邮件正文 (可自由编辑)", value=tpl["body"].format(company=lead['公司名'], product=lead['匹配产品']), height=200, key=f"body_{i}")
                
                # C) 操作按钮组
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("🚀 立即 SMTP 发送", key=f"send_{i}", type="primary"):
                        if not target_email:
                            st.error("请输入收件人邮箱")
                        else:
                            with st.spinner("正在发送..."):
                                success, msg = send_smtp_email(target_email, mail_sub, mail_body)
                                if success:
                                    st.success("✅ 邮件已成功发送！")
                                    db.log_email({"邮件ID": f"MAIL_{int(time.time())}", "客户公司": lead['公司名'], "收件人": target_email, "发送时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "主题": mail_sub, "内容摘要": mail_body[:50]+"...", "状态": "成功"})
                                else:
                                    st.error(msg)
                with c2:
                    # Streamlit 代码块自带原生复制按钮
                    st.code(f"Subject: {mail_sub}\n\n{mail_body}", language="text")
                    st.caption("☝️ 悬浮在框右上角点击一键复制")
                with c3:
                    if st.button("🔖 仅标记为已联系", key=f"mark_{i}"):
                        db.log_email({"邮件ID": f"MAIL_{int(time.time())}", "客户公司": lead['公司名'], "收件人": target_email, "发送时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "主题": mail_sub, "内容摘要": "(手动复制发送)", "状态": "手动标记发送"})
                        st.success("已记录到发送追踪历史！")
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
                st.success("录入成功！刷新页面可见。")

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
