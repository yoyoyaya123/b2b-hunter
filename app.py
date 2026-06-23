import streamlit as st
import requests
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ddgs import DDGS
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

# ==================== 全球9国配置（保持不变，此处省略，请使用之前完整的字典） ====================
COUNTRY_CONFIG = { ... }  # 请用你之前完整的9个国家配置替换这里

# ==================== 辅助函数（保持不变） ====================
def get_image_features(image): ...
def classify_image(image, product_line_names): ...
def fetch_page(url, retries=2): ...
def extract_info(html, url, exclude_words, keywords): ...
def get_website_images(html, base_url, max_images=3): ...
def download_image(img_url, timeout=8): ...
def compute_similarity(user_features, website_images): ...
def duckduckgo_search(query, region, max_results=5): ...

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
    # ... 图片处理逻辑（不变）
    # ... 关键词设置逻辑（不变）

    st.markdown("---")
    st.caption("已排除公司域名数: " + str(len(st.session_state.excluded_domains)))
    if st.button("清空排除列表，重新开始", key="clear_excluded"):
        st.session_state.excluded_domains.clear()
        st.session_state.search_count = 0
        st.rerun()

# ==================== 搜索主逻辑（不变） ====================
def search_and_collect_leads(keywords, config, excluded_domains, user_features=None, max_new=5):
    # ... 与之前一致

if st.button("🔍 搜索5家新公司", type="primary"):
    # ... 搜索逻辑

# ==================== 显示结果（已修复） ====================
if 'last_leads' in st.session_state:
    leads = st.session_state.last_leads
    for i, lead in enumerate(leads, 1):
        st.subheader(f"{i}. {lead['公司名称']}")
        st.markdown(f"🌐 官网: [{lead['官网']}]({lead['官网']})")
        st.markdown(f"🔧 匹配产品: {lead['匹配产品']}")
        st.markdown(f"📞 联系方式: {lead['联系方式']}")

        if lead.get('网站图片'):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.session_state.uploaded_images:
                    st.image(st.session_state.uploaded_images[0], caption="你的产品", width=200, key=f"user_img_{i}")
            with col2:
                st.image(lead['网站图片'], caption="客户网站图片", width=200, key=f"web_img_{i}")
            with col3:
                st.metric("图片相似度", lead.get('相似度', 'N/A'), key=f"metric_{i}")
        else:
            st.caption("未找到可对比的产品图片")
        st.markdown("---")

    df = pd.DataFrame(leads)
    df = df[['公司名称', '官网', '匹配产品', '联系方式', '相似度']]
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下载本次结果 CSV", csv, f"leads_{st.session_state.search_count}.csv", "text/csv", key=f"download_{st.session_state.search_count}")
else:
    st.info("点击上方按钮开始搜索，每次返回5家不重复的公司")
