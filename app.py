import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json

# -------------------------------
# 💾 1. 데이터 저장 (예수금/수동시세는 여전히 JSON에 저장하여 유지)
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
# 📱 2. 화면 구성
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오 (Google Sheets 연동)", layout="centered")

# -------------------------------
# 📂 3. 구글 시트 데이터 로드 함수
# -------------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv&gid=0"

@st.cache_data(ttl=10) # 10초마다 시트에서 새 데이터를 읽어옴
def load_sheet_data():
    try:
        # 구글 시트를 CSV 형태로 직접 읽어옵니다.
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error("구글 시트를 불러올 수 없습니다. '링크가 있는 모든 사용자에게 공개' 설정을 확인해 주세요.")
        return pd.DataFrame()

# -------------------------------
# 📂 4. 사이드바 및 계좌 선택
# -------------------------------
st.sidebar.title("📂 계좌 관리")
db = load_data()

# 구글 시트에서 전체 데이터 로드
raw_df = load_sheet_data()

if not raw_df.empty:
    # '계좌' 컬럼이 있다면 계좌별 필터링, 없다면 전체 표시
    if "계좌" in raw_df.columns:
        accounts = ["전체 계좌"] + sorted(raw_df["계좌"].unique().tolist())
    else:
        accounts = ["전체 계좌"]
    
    selected_account = st.sidebar.selectbox("표시할 계좌를 선택하세요", accounts)
    
    if selected_account == "전체 계좌":
        df = raw_df
    else:
        df = raw_df[raw_df["계좌"] == selected_account]
else:
    st.stop()

st.title(f"📊 {selected_account} 포트폴리오")
st.info("💡 구글 시트에서 데이터를 수정하면 10초 내에 앱에 자동 반영됩니다.")

# -------------------------------
# 💰 5. 예수금 설정 (기존 로직 유지)
# -------------------------------
current_acc_name = selected_account if selected_account != "전체 계좌" else "기본 계좌"
saved_cash = db["cash"].get(current_acc_name, 1000000)
cash = st.number_input(f"💰 {current_acc_name} 예수금 설정", value=int(saved_cash), step=10000)
if cash != saved_cash:
    db["cash"][current_acc_name] = cash
    save_data(db)

# -------------------------------
# 🔹 6. 시세 크롤링 및 포트폴리오 계산
# -------------------------------
@st.cache_data(ttl=10)
def get_price(code):
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={str(code).zfill(6)}"
        res = requests.get(url, timeout=3)
        soup = BeautifulSoup(res.text, "html.parser")
        price_tag = soup.select_one(".no_today .blind")
        return int(price_tag.text.replace(",", "")) if price_tag else 0
    except: return 0

portfolio = {}
for _, row in df.iterrows():
    try:
        name, qty, p, action = row["종목"], row["수량"], row["가격"], row["구분"]
        code = str(row["코드"]).zfill(6)
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
# 💹 7. 시세 및 결과 출력 (카드 및 테이블)
# -------------------------------
price_dict = {}
if active_stocks:
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        data = portfolio[name]
        saved_p = db["manual_prices"].get(name)
        auto_p = get_price(data["code"])
        init_val = saved_p if saved_p else (auto_p if auto_p > 0 else int(data["total_buy"]/data["qty"]))
        
        with cols[i % 4]:
            p_input = st.number_input(name, value=int(init_val), key=f"inp_{name}")
            if p_input != saved_p:
                db["manual_prices"][name] = p_input
                save_data(db)
            price_dict[name] = p_input

    # 요약 계산 및 출력 (기존 카드 디자인 동일)
    # ... [이전 카드 및 테이블 출력 코드와 동일하여 생략함] ...
    # (실제 적용 시에는 이전 코드의 집계 및 출력 부분을 그대로 붙여넣으시면 됩니다.)