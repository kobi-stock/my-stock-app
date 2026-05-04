import pandas as pd
import streamlit as st
import requests
import os
import json
import re

# 💾 1. 데이터 관리
DATA_FILE = "portfolio_data.json"
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                for key in ["cash", "manual_prices", "api_keys"]:
                    if key not in data: data[key] = {}
                return data
        except: return {"cash": {}, "manual_prices": {}, "api_keys": {}}
    return {"cash": {}, "manual_prices": {}, "api_keys": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'db' not in st.session_state:
    st.session_state.db = load_data()

# 💹 2. 시세 엔진 (가격을 고정하기 위해 캐시 시간을 대폭 늘림)
@st.cache_data(ttl=300) # 5분 동안 시세 고정
def fetch_live_price(code):
    if not code or pd.isna(code): return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except: return 0

# 📱 3. UI 설정
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
st.markdown("<style>[data-testid='stMetricValue'] { font-size: 1.4rem !important; }</style>", unsafe_allow_html=True)

# 📂 4. 데이터 로드 및 계좌 선택 (전체 계좌 복구)
st.sidebar.title("🛠️ 설정")
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
account_list = ["전체 계좌"] + list(TAB_INFO.keys())
selected_account = st.sidebar.selectbox("계좌 선택", account_list)

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    url = f"https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv&gid={gid}"
    try: return pd.read_csv(url, dtype=str)
    except: return pd.DataFrame()

# 데이터 통합 로직
if selected_account == "전체 계좌":
    dfs = []
    total_cash = 0
    for name, gid in TAB_INFO.items():
        dfs.append(load_sheet_data(gid))
        total_cash += int(st.session_state.db["cash"].get(name, 0))
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    cash = total_cash
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
        name = str(row.iloc[1]).strip()
        if not name or name == "nan": continue
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4]).strip()
        code = str(row.iloc[5])
        if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * price
        elif action == "매도":
            avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"] if portfolio[name]["qty"] > 0 else 0
            portfolio[name]["qty"] -= qty
            portfolio[name]["total_buy"] -= avg_p * qty

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 🏦 6. 메인 화면
st.title(f"📊 {selected_account} 현황")

price_dict = {}
if active_stocks:
    # 시세 수동 수정 (가격 고정용)
    with st.expander("💹 시세 수동 수정 (입력 시 가격 고정)", expanded=False):
        cols = st.columns(3)
        for i, name in enumerate(active_stocks):
            live_p = fetch_live_price(portfolio[name]["code"])
            saved_p = st.session_state.db["manual_prices"].get(name)
            display_val = saved_p if saved_p is not None else live_p
            with cols[i % 3]:
                p_in = st.number_input(f"{name}", value=int(display_val), key=f"p_{name}")
                if p_in != display_val:
                    st.session_state.db["manual_prices"][name] = p_in
                    save_data(st.session_state.db)
                price_dict[name] = p_in

    total_eval = sum(portfolio[name]["qty"] * price_dict[name] for name in active_stocks)
    total_buy_sum = sum(portfolio[name]["total_buy"] for name in active_stocks)
    total_asset = cash + total_eval
    total_profit = total_eval - total_buy_sum
    total_rate = (total_profit / total_buy_sum * 100) if total_buy_sum > 0 else 0

    st.divider()

    # ✨ 레이아웃: 3개씩 두 줄
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 예수금", f"{int(cash):,}원")
    c2.metric("📥 총매수액", f"{int(total_buy_sum):,}원")
    c3.metric("💵 총수익", f"{int(total_profit):+,}원", f"{total_rate:+.2f}%")

    c4, c5, c6 = st.columns(3)
    c4.metric("📈 총평가액", f"{int(total_eval):,}원")
    c5.metric("🏦 총자산", f"{int(total_asset):,}원")
    c6.metric("📊 수익률", f"{total_rate:+.2f}%")

    st.divider()

    # 📋 7. 종목 현황 표 (현재가 포함)
    res_list = []
    for name in active_stocks:
        d = portfolio[name]
        curr_p = price_dict[name]
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        res_list.append({
            "종목": name, "수량": float(d["qty"]), "평단": float(avg_p), 
            "현재가": float(curr_p), "평가액": float(eval_amt), 
            "수익률": float((curr_p-avg_p)/avg_p*100), "비중(%)": float(eval_amt/total_asset*100)
        })
    # 예수금 추가
    res_list.append({
        "종목": "💰 예수금", "수량": 0, "평단": 0, "현재가": 0, 
        "평가액": float(cash), "수익률": 0, "비중(%)": float(cash/total_asset*100)
    })
    
    st.dataframe(pd.DataFrame(res_list).style.format({
        "수량": lambda x: f"{int(x):,}" if x > 0 else "-",
        "평단": lambda x: f"{int(x):,}" if x > 0 else "-",
        "현재가": lambda x: f"{int(x):,}" if x > 0 else "-", # 현재가 포맷 복구
        "평가액": "{:,.0f}", "수익률": "{:+.2f}%", "비중(%)": "{:.2f}%"
    }), width="stretch", hide_index=True)
else:
    st.info("표시할 종목이 없습니다.")