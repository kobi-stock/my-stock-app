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
                if "cash" not in data: data["cash"] = {}
                return data
        except: return {"cash": {}}
    return {"cash": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'db' not in st.session_state:
    st.session_state.db = load_data()
db = st.session_state.db

# 💹 2. 실시간 시세 엔진 (상단 카드용)
@st.cache_data(ttl=5)
def get_live_price(code):
    if not code or pd.isna(code): return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except: return 0

# 📱 3. 화면 설정 및 스타일
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
st.markdown("""
<style>
    h1 { font-size: 1.5rem !important; }
    h3 { font-size: 1.1rem !important; }
    .card-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 15px; }
    .custom-card {
        background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px;
        padding: 10px; min-width: 100px; flex: 1 1 calc(23% - 8px);
        box-shadow: 1px 1px 3px rgba(0,0,0,0.05); text-align: center;
    }
    .card-label { font-size: 0.75rem; color: #6c757d; margin-bottom: 4px; }
    .card-value { font-size: 0.95rem; font-weight: 700; color: #212529; }
    .card-delta { font-size: 0.75rem; font-weight: 600; margin-top: 2px; }
    .up { color: #e63946 !important; }
    .down { color: #457b9d !important; }
</style>
""", unsafe_allow_html=True)

# 📂 4. 구글 시트 데이터 로드
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
HISTORY_GID = "144293082" # 히스토리 탭 GID

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str).fillna('')
    except: return pd.DataFrame()

def parse_date_flexible(s):
    try:
        s = re.sub(r'[^0-9\.]', '', str(s)).strip('.')
        parts = s.split('.')
        return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except: return None

# 🔐 데이터 처리
st.sidebar.title("🔐 계좌 설정")
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

portfolio = {}
total_cash = 0

for name, gid in TAB_INFO.items():
    if selected_account != "전체 계좌" and selected_account != name: continue
    df_acc = load_sheet_data(gid)
    if df_acc.empty: continue
    for _, row in df_acc.iterrows():
        item_name = str(row.iloc[1]).strip()
        if not item_name or item_name in ["종목", "nan"]: continue
        if "예수금" in item_name:
            total_cash += pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
            continue
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        code = str(row.iloc[5]).strip()
        if item_name not in portfolio: portfolio[item_name] = {"qty": qty, "buy_amt": qty * price, "code": code}

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 1️⃣ 화면 출력
st.title(f"📊 {selected_account}")

# 2️⃣ 상단 실시간 현재가 카드 (복구됨)
if active_stocks:
    st.subheader("💹 실시간 종목 시세")
    price_dict = {n: get_live_price(portfolio[n]["code"]) for n in active_stocks}
    stock_html = '<div class="card-container">'
    for name in active_stocks:
        stock_html += f'<div class="custom-card"><div class="card-label">{name}</div><div class="card-value">{price_dict[name]:,}</div></div>'
    st.markdown(stock_html + '</div>', unsafe_allow_html=True)

# 3️⃣ 계좌 변동 요약 (시트 데이터 기반 정확한 계산)
st.divider()
st.subheader("📈 계좌 변동 및 요약")

df_history = load_sheet_data(HISTORY_GID)

def get_comparison_from_sheet(days):
    if df_history.empty: return 0, 0.0
    h = df_history.copy()
    h['dt'] = h.iloc[:, 0].apply(parse_date_flexible)
    h = h.dropna(subset=['dt']).sort_values('dt', ascending=False)
    
    # 5월 6일(오늘)과 5월 5일(어제) 데이터를 시트에서 직접 가져옴
    today_rec = h[h['dt'] == datetime.date(2026, 5, 6)]
    past_date = datetime.date(2026, 5, 6) - datetime.timedelta(days=days)
    past_rec = h[h['dt'] <= past_date].head(1)
    
    if today_rec.empty or past_rec.empty: return 0, 0.0
    
    def get_val(row):
        if selected_account == "전체 계좌":
            return (pd.to_numeric(str(row.iloc[0, 1]).replace(',', ''), errors='coerce') or 0) + \
                   (pd.to_numeric(str(row.iloc[0, 2]).replace(',', ''), errors='coerce') or 0)
        col = 1 if selected_account == "기본 계좌" else 2
        return pd.to_numeric(str(row.iloc[0, col]).replace(',', ''), errors='coerce') or 0

    curr_val = get_val(today_rec)
    prev_val = get_val(past_rec)
    diff = curr_val - prev_val
    return diff, (diff / prev_val * 100) if prev_val != 0 else 0

metrics_html = '<div class="card-container">'
for label, d in [("전일대비", 1), ("전주대비", 7), ("전월대비", 30)]:
    v, r = get_comparison_from_sheet(d)
    cls = "up" if v > 0 else "down" if v < 0 else ""
    metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(v):+,}</div><div class="card-delta {cls}">{r:+.2f}%</div></div>'
st.markdown(metrics_html + '</div>', unsafe_allow_html=True)

# 4️⃣ 상세 리스트
st.divider()
st.subheader("📋 보유 종목 리스트")
if active_stocks:
    res = []
    total_eval_sum = 0
    for n in active_stocks:
        cp = price_dict[n]
        ba = portfolio[n]["buy_amt"] / portfolio[n]["qty"]
        ev = portfolio[n]["qty"] * cp
        total_eval_sum += ev
        res.append([n, portfolio[n]["qty"], int(ba), cp, int(ev), ((cp-ba)/ba*100)])
    
    df_res = pd.DataFrame(res, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률"])
    st.dataframe(df_res.style.format({"수량":"{:,.0f}","평단":"{:,.0f}","현재가":"{:,.0f}","평가액":"{:,.0f}","수익률":"{:+.2f}%"}), use_container_width=True, hide_index=True)
else:
    st.info("보유 종목이 없습니다.")