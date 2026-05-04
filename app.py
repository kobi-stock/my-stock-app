import pandas as pd
import streamlit as st
import requests
import os
import json
import re
import datetime

# 💾 1. 데이터 저장 및 로드
DATA_FILE = "portfolio_data.json"
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                for key in ["cash", "manual_prices", "api_keys", "history"]:
                    if key not in data: data[key] = {}
                return data
        except: return {"cash": {}, "manual_prices": {}, "api_keys": {}, "history": {}}
    return {"cash": {}, "manual_prices": {}, "api_keys": {}, "history": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'db' not in st.session_state:
    st.session_state.db = load_data()

# 💹 2. 시세 엔진 (무조건 숫자를 반환하도록 강화)
def fetch_live_price(code):
    if not code or pd.isna(code): return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except: return 0

# 📱 3. UI 설정
st.set_page_config(page_title="주식 포트폴리오", layout="wide") # 넓게 보기

# 🛠️ 4. 사이드바 (API 및 예수금)
st.sidebar.title("🛠️ 설정")
with st.sidebar.expander("🔐 한투 API 설정"):
    ak = st.text_input("App Key", value=st.session_state.db["api_keys"].get("key", ""), type="password")
    as_ = st.text_input("App Secret", value=st.session_state.db["api_keys"].get("secret", ""), type="password")
    if st.button("저장"):
        st.session_state.db["api_keys"] = {"key": ak, "secret": as_}
        save_data(st.session_state.db)

TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

@st.cache_data(ttl=5)
def load_sheet_data(gid):
    url = f"https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv&gid={gid}"
    try: return pd.read_csv(url, dtype=str)
    except: return pd.DataFrame()

# 데이터 및 예수금 로드
if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    cash = sum(int(st.session_state.db["cash"].get(name, 0)) for name in TAB_INFO.keys())
else:
    df = load_sheet_data(TAB_INFO[selected_account])
    saved_cash = int(st.session_state.db["cash"].get(selected_account, 0))
    cash = st.sidebar.number_input(f"💰 {selected_account} 예수금", value=saved_cash, step=10000)
    if cash != saved_cash:
        st.session_state.db["cash"][selected_account] = cash
        save_data(st.session_state.db)

# 📊 5. 포트폴리오 계산
portfolio = {}
if not df.empty:
    for _, row in df.iterrows():
        try:
            name = str(row.iloc[1]).strip()
            if not name or name == "nan" or name == "종목": continue
            qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
            price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
            action = str(row.iloc[4]).strip()
            code = str(row.iloc[5])
            
            if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
            if "매수" in action:
                portfolio[name]["qty"] += qty
                portfolio[name]["total_buy"] += qty * price
            elif "매도" in action:
                avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"] if portfolio[name]["qty"] > 0 else 0
                portfolio[name]["qty"] -= qty
                portfolio[name]["total_buy"] -= avg_p * qty
        except: continue

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 🏦 6. 메인 화면
st.title(f"📊 {selected_account} 자산 현황")

price_dict = {}
if active_stocks:
    # 3개씩 두 줄 레이아웃 계산용
    for name in active_stocks:
        live_p = fetch_live_price(portfolio[name]["code"])
        saved_p = st.session_state.db["manual_prices"].get(name)
        price_dict[name] = saved_p if saved_p is not None else live_p

    total_eval = sum(portfolio[name]["qty"] * price_dict[name] for name in active_stocks)
    total_buy_sum = sum(portfolio[name]["total_buy"] for name in active_stocks)
    total_asset = cash + total_eval
    total_profit = total_eval - total_buy_sum
    total_rate = (total_profit / total_buy_sum * 100) if total_buy_sum > 0 else 0

    # ✨ 지표 레이아웃 (3개씩 두 줄)
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 예수금", f"{int(cash):,}원")
    c2.metric("📥 총매수액", f"{int(total_buy_sum):,}원")
    c3.metric("💵 총수익", f"{int(total_profit):+,}원", f"{total_rate:+.2f}%")

    c4, c5, c6 = st.columns(3)
    c4.metric("📈 총평가액", f"{int(total_eval):,}원")
    c5.metric("🏦 총자산", f"{int(total_asset):,}원")
    c6.metric("📊 수익률", f"{total_rate:+.2f}%")

    st.divider()

    # 📋 7. 종목 상세 표 (현재가 고정 및 색상 적용)
    st.markdown("#### 📋 보유 종목 상세 (현재가 포함)")
    res_list = []
    for name in active_stocks:
        d = portfolio[name]
        curr_p = price_dict[name]
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        profit_rate = ((curr_p - avg_p) / avg_p * 100) if avg_p > 0 else 0
        
        res_list.append({
            "종목": name,
            "수량": int(d["qty"]),
            "평단": int(avg_p),
            "현재가": int(curr_p), # 이 열이 무조건 생성됨
            "평가액": int(eval_amt),
            "수익률": round(profit_rate, 2),
            "비중": round(eval_amt / total_asset * 100, 1)
        })
    
    # 데이터프레임 생성
    final_df = pd.DataFrame(res_list)

    # 수익률 색상 스타일 함수
    def color_profit(val):
        color = 'red' if val > 0 else 'blue' if val < 0 else 'black'
        return f'color: {color}; font-weight: bold'

    st.dataframe(
        final_df.style.format({
            "수량": "{:,}", "평단": "{:,}", "현재가": "{:,}", 
            "평가액": "{:,}", "수익률": "{:+.2f}%", "비중": "{:.1f}%"
        }).map(color_profit, subset=["수익률"]),
        use_container_width=True,
        hide_index=True
    )

    # 시세 수정 (하단 배치)
    with st.expander("💹 시세 수동 수정"):
        scols = st.columns(4)
        for i, name in enumerate(active_stocks):
            with scols[i % 4]:
                new_p = st.number_input(f"{name}", value=int(price_dict[name]), key=f"edit_{name}")
                if new_p != price_dict[name]:
                    st.session_state.db["manual_prices"][name] = new_p
                    save_data(st.session_state.db)
                    st.rerun()