import pandas as pd
import streamlit as st
import requests
import os
import json
import datetime
import re

# 💾 1. 데이터 관리
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                for key in ["cash", "api_keys", "history"]:
                    if key not in data: data[key] = {}
                return data
        except:
            return {"cash": {}, "api_keys": {}, "history": {}}
    return {"cash": {}, "api_keys": {}, "history": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'db' not in st.session_state:
    st.session_state.db = load_data()

db = st.session_state.db

# 💹 2. 실시간 시세 엔진
@st.cache_data(ttl=5)
def get_live_price(code):
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except:
        return 0

# 📱 3. UI 설정
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
st.markdown("<style>[data-testid='stMetricValue'] { font-size: 1.4rem !important; }</style>", unsafe_allow_html=True)

# 🔐 4. 사이드바 설정
st.sidebar.title("🔐 설정")
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

# 📂 5. 데이터 로드
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
    except: return pd.DataFrame()

if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
    cash = sum([int(db["cash"].get(acc, 0)) for acc in TAB_INFO.keys()])
else:
    df = load_sheet_data(TAB_INFO[selected_account])
    saved_cash = db["cash"].get(selected_account, 0)
    cash = st.sidebar.number_input(f"💰 {selected_account} 예수금", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

if df.empty: st.warning("데이터가 없습니다."); st.stop()

# 📊 6. 포트폴리오 계산
portfolio = {}
for _, row in df.iterrows():
    name = str(row.iloc[1]).strip()
    if not name or name == "nan" or name == "종목": continue
    qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
    price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
    action = str(row.iloc[4]).strip()
    code = str(row.iloc[5])
    if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
    if action == "매수":
        portfolio[name]["qty"] += qty
        portfolio[name]["total_buy"] += qty * price
    elif action == "매도" and portfolio[name]["qty"] > 0:
        avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
        portfolio[name]["qty"] -= qty
        portfolio[name]["total_buy"] -= avg_p * qty

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 🏦 7. 결과 출력
st.title(f"📊 {selected_account} 현황")

if active_stocks:
    total_eval, total_buy_sum, result_list = 0, 0, []
    for name in active_stocks:
        d = portfolio[name]
        curr_p = get_live_price(d["code"]) # 실시간 현재가 가져오기
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        total_eval += eval_amt
        total_buy_sum += d["total_buy"]
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        # 리스트에 '현재가' 데이터 명시적 추가[cite: 1]
        result_list.append([name, d["qty"], int(avg_p), int(curr_p), int(eval_amt), round(profit_r, 2)])

    total_asset = cash + total_eval
    
    # 히스토리 기록 및 변동량 계산[cite: 1]
    today = datetime.date.today().isoformat()
    db["history"][today] = total_asset
    save_data(db)

    def get_change(days):
        target_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        past_dates = sorted([d for d in db["history"].keys() if d <= target_date], reverse=True)
        if not past_dates: return 0.0, 0
        past_val = db["history"][past_dates[0]]
        return (total_asset - past_val) / past_val * 100, total_asset - past_val

    # 📈 상단 변동 지표
    m1, m2, m3 = st.columns(3)
    d_rate, d_val = get_change(1); w_rate, w_val = get_change(7); m_rate, m_val = get_change(30)
    m1.metric("전일 대비", f"{int(d_val):+,}원", f"{d_rate:+.2f}%")
    m2.metric("전주 대비", f"{int(w_val):+,}원", f"{w_rate:+.2f}%")
    m3.metric("전월 대비", f"{int(m_val):+,}원", f"{m_rate:+.2f}%")
    st.divider()

    # 💰 계좌 요약 (3x2)
    total_profit_amt = total_eval - total_buy_sum
    total_profit_rate = (total_profit_amt / total_buy_sum * 100) if total_buy_sum > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 예수금", f"{int(cash):,}원")
    c2.metric("📥 총매수액", f"{int(total_buy_sum):,}원")
    c3.metric("💵 총수익", f"{int(total_profit_amt):+,}원", f"{total_profit_rate:+.2f}%")

    c4, c5, c6 = st.columns(3)
    c4.metric("📈 총평가액", f"{int(total_eval):,}원")
    c5.metric("🏦 총자산", f"{int(total_asset):,}원")
    c6.metric("📊 수익률", f"{total_profit_rate:+.2f}%")
    st.divider()

    # 📋 보유 종목 현황 (현재가 항목 포함 및 색상 적용)[cite: 1]
    st.markdown("### 📋 보유 종목 현황")
    final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1)] for r in result_list]
    df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    def color_profit(val):
        color = '#e63946' if val > 0 else '#457b9d' if val < 0 else 'black'
        return f'color: {color}; font-weight: bold;'

    st.dataframe(df_final.style.format({
        "수량": "{:,.0f}", "평단": "{:,.0f}", "현재가": "{:,.0f}", 
        "평가액": "{:,.0f}", "수익률": "{:+.2f}%", "비중(%)": "{:.1f}%"
    }).map(color_profit, subset=['수익률']), use_container_width=True, hide_index=True)
else:
    st.info("보유 종목이 없습니다.")