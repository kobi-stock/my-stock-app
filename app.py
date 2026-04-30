import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json

# -------------------------------
# 💾 1. 데이터 저장 및 로드
# -------------------------------
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"cash": {}, "manual_prices": {}}
    return {"cash": {}, "manual_prices": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# -------------------------------
# 📱 2. 화면 구성 및 스타일
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오 관리", layout="wide") # 넓게 보기 설정
st.markdown("""
<style>
.main .block-container { max-width: 1100px; padding-top: 2rem; }
div.stNumberInput > label { font-weight: bold; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# 📂 3. 구글 시트 탭 정보 설정
# -------------------------------
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {
    "기본 계좌": "0",
    "한국투자증권": "1939408144"
}

@st.cache_data(ttl=5) # 5초마다 시트 갱신
def load_sheet_data(gid):
    try:
        url = f"{SHEET_BASE}&gid={gid}"
        df = pd.read_csv(url, dtype={'코드': str})
        return df
    except Exception as e:
        st.error(f"⚠️ 시트 로드 실패: {e}")
        return pd.DataFrame()

# -------------------------------
# 📂 4. 사이드바 및 초기화 버튼
# -------------------------------
st.sidebar.title("📂 계좌 관리")
selected_account = st.sidebar.selectbox("표시할 계좌를 선택하세요", ["전체 계좌"] + list(TAB_INFO.keys()))

db = load_data()

# [중요] 저장된 수동 가격 초기화 버튼
if st.sidebar.button("🔄 저장된 수동 가격 초기화"):
    db["manual_prices"] = {}
    save_data(db)
    st.sidebar.success("수동 입력 가격이 모두 지워졌습니다. 실시간 시세를 가져옵니다.")
    st.rerun()

# 데이터 로드
if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
else:
    df = load_sheet_data(TAB_INFO[selected_account])

if df.empty:
    st.stop()

# -------------------------------
# 🔹 5. 실시간 시세 크롤링 (성능 개선)
# -------------------------------
@st.cache_data(ttl=10) # 10초 캐시
def get_live_price(code):
    if not code or str(code) == "nan": return 0
    try:
        clean_code = str(code).split('.')[0].zfill(6)
        url = f"https://finance.naver.com/item/main.nhn?code={clean_code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=2)
        soup = BeautifulSoup(res.text, "html.parser")
        price_tag = soup.select_one(".no_today .blind")
        return int(price_tag.text.replace(",", "")) if price_tag else 0
    except: return 0

# -------------------------------
# 📊 6. 포트폴리오 계산
# -------------------------------
portfolio = {}
for _, row in df.iterrows():
    try:
        name, qty, p, action = row["종목"], row["수량"], row["가격"], row["구분"]
        code = str(row["코드"]).split('.')[0].zfill(6)
        if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * p
        elif action == "매도":
            if portfolio[name]["qty"] > 0:
                avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
                portfolio[name]["qty"] -= qty
                portfolio[name]["total_buy"] -= avg_p * qty
    except: continue

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# -------------------------------
# 💹 7. 시세 입력창 (실시간 시세 표시 강화)
# -------------------------------
st.title(f"📊 {selected_account}")
price_dict = {}

if active_stocks:
    st.markdown("### 💹 현재 시세 확인 및 수정")
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        data = portfolio[name]
        live_p = get_live_price(data["code"]) # 실시간 네이버 시세
        saved_p = db["manual_prices"].get(name) # 이전에 수동으로 적었던 시세
        
        # 현재 화면에 보여줄 값 결정 (수동 입력이 있으면 수동 입력값, 없으면 실시간 시세)
        display_val = saved_p if saved_p else live_p
        
        with cols[i % 4]:
            # 도움말에 실시간 시세 정보를 보여줌
            p_input = st.number_input(f"{name} (실시간: {live_p:,}원)", value=int(display_val), key=f"p_{name}")
            if p_input != saved_p and p_input != live_p:
                db["manual_prices"][name] = p_input
                save_data(db)
            price_dict[name] = p_input

    # -------------------------------
    # 📈 8. 계좌 요약 및 테이블 (기존 동일)
    # -------------------------------
    # (이하 생략 - 이전 답변의 요약 카드 및 테이블 출력 코드와 동일)
    # 총수익, 총자산 계산 로직 포함...