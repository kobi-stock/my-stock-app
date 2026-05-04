import pandas as pd
import streamlit as st
import requests
import os
import json
import datetime
import re

# 💾 1. 데이터 관리[cite: 1]
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

# 💹 2. 실시간 시세 엔진[cite: 1]
@st.cache_data(ttl=5)
def get_live_price(code):
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except:
        return 0

# 📱 3. 화면 설정 및 모바일 최적화 스타일[cite: 1]
st.set_page_config(page_title="주식 포트폴리오", layout="centered")

# CSS 정의 (HTML로 직접 렌더링될 부분)[cite: 1]
style_css = """
<style>
    h1 { font-size: 1.5rem !important; }
    h3 { font-size: 1.1rem !important; }
    .card-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-start;
        margin-bottom: 15px;
    }
    .custom-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 10px;
        min-width: 120px;
        flex: 1 1 calc(33.3% - 8px);
        box-shadow: 1px 1px 3px rgba(0,0,0,0.05);
        text-align: center;
    }
    @media (max-width: 480px) {
        .custom-card { flex: 1 1 calc(50% - 8px); }
    }
    .card-label { font-size: 0.75rem; color: #6c757d; margin-bottom: 4px; }
    .card-value { font-size: 1rem; font-weight: 700; color: #212529; }
    .card-delta { font-size: 0.75rem; font-weight: 600; margin-top: 2px; }
    .up { color: #e63946; }
    .down { color: #457b9d; }
</style>
"""
st.markdown(style_css, unsafe_allow_html=True) # CSS 적용[cite: 1]

# 📂 4. 데이터 로드 설정[cite: 1]
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
    except: return pd.DataFrame()

st.sidebar.title("🔐 계좌 설정")
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
    total_cash = sum([int(db["cash"].get(acc, 0)) for acc in TAB_INFO.keys()])
else:
    df = load_sheet_data(TAB_INFO[selected_account])
    total_cash = int(db["cash"].get(selected_account, 0))

# 포트폴리오 계산[cite: 1]
portfolio = {}
if not df.empty:
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

# =========================================================
# 1️⃣ 예수금 입력[cite: 1]
# =========================================================
st.title(f"📊 {selected_account}")
if selected_account != "전체 계좌":
    new_cash = st.number_input(f"💰 예수금 입력", value=total_cash, step=10000)
    if new_cash != total_cash:
        db["cash"][selected_account] = new_cash
        save_data(db)
        st.rerun()

# =========================================================
# 2️⃣ 실시간 종목 시세 카드[cite: 1]
# =========================================================
price_dict = {}
if active_stocks:
    st.subheader("💹 실시간 종목 시세")
    stock_html = '<div class="card-container">'
    for name in active_stocks:
        live_p = get_live_price(portfolio[name]["code"])
        price_dict[name] = live_p
        stock_html += f'<div class="custom-card"><div class="card-label">{name}</div><div class="card-value">{live_p:,}</div></div>'
    stock_html += '</div>'
    
    # 중요: 반드시 st.markdown으로 출력[cite: 1]
    st.markdown(stock_html, unsafe_allow_html=True) 

    # 자산 데이터 계산[cite: 1]
    total_eval, total_buy_sum, result_list = 0, 0, []
    for name in active_stocks:
        d = portfolio[name]
        curr_p = price_dict[name]
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        total_eval += eval_amt
        total_buy_sum += d["total_buy"]
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        result_list.append([name, d["qty"], int(avg_p), int(curr_p), int(eval_amt), round(profit_r, 2)])

    total_asset = total_cash + total_eval
    today = datetime.date.today().isoformat()
    db["history"][today] = total_asset
    save_data(db)

    # =========================================================
    # 3️⃣ 계좌 변동 및 요약 카드[cite: 1]
    # =========================================================
    st.divider()
    st.subheader("📈 계좌 변동 및 요약")
    
    def get_change(days):
        target_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        past_dates = sorted([d for d in db["history"].keys() if d <= target_date], reverse=True)
        if not past_dates: return 0.0, 0
        past_val = db["history"][past_dates[0]]
        return (total_asset - past_val) / past_val * 100, total_asset - past_val

    d_rate, d_val = get_change(1); w_rate, w_val = get_change(7); m_rate, m_val = get_change(30)
    t_profit_rate = ((total_eval - total_buy_sum) / total_buy_sum * 100) if total_buy_sum > 0 else 0

    metrics_html = '<div class="card-container">'
    # 변동 항목 3개
    for label, val, rate in [("전일대비", d_val, d_rate), ("전주대비", w_val, w_rate), ("전월대비", m_val, m_rate)]:
        cls = "up" if val >= 0 else "down"
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(val):+,}</div><div class="card-delta {cls}">{rate:+.2f}%</div></div>'
    
    # 요약 항목 4개
    summary = [("💰 예수금", total_cash), ("📥 총매수액", total_buy_sum), ("🏦 총자산", total_asset), ("📊 총수익률", t_profit_rate)]
    for label, val in summary:
        display_val = f"{val:+.2f}%" if "수익률" in label else f"{int(val):,}"
        cls = ("up" if val >= 0 else "down") if "수익률" in label else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value {cls}">{display_val}</div></div>'
    metrics_html += '</div>'
    
    # 중요: 반드시 st.markdown으로 출력[cite: 1]
    st.markdown(metrics_html, unsafe_allow_html=True) 

    # =========================================================
    # 4️⃣ 보유 종목 리스트 (표)[cite: 1]
    # =========================================================
    st.divider()
    st.subheader("📋 보유 종목 리스트")
    final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1)] for r in result_list]
    final_data.append(["💰 예수금", None, None, None, int(total_cash), None, round(total_cash/total_asset*100, 1)])
    
    df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    st.dataframe(df_final.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}",
        "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-",
        "비중(%)": "{:.1f}%"
    }), use_container_width=True, hide_index=True)

else:
    st.info("보유 종목이 없습니다.")