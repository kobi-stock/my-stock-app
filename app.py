import pandas as pd
import streamlit as st
import requests
import os
import json
import datetime
import re

# 💾 1. 데이터 관리 (예수금 저장용 유지)
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

# 💹 2. 실시간 시세 엔진
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
    @media (max-width: 480px) { .custom-card { flex: 1 1 calc(50% - 8px); } }
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

# 계좌 선택 및 데이터 통합
st.sidebar.title("🔐 계좌 설정")
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

portfolio = {}
total_cash = 0

# 계좌 데이터 로드
for name, gid in TAB_INFO.items():
    if selected_account != "전체 계좌" and selected_account != name: continue
    df_acc = load_sheet_data(gid)
    if df_acc.empty: continue
    
    for _, row in df_acc.iterrows():
        item_name = str(row.iloc[1]).strip()
        if not item_name or item_name in ["종목", "nan"]: continue
        
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4]).strip()
        code = str(row.iloc[5]).strip()

        if "예수금" in item_name:
            total_cash += price
            continue

        if item_name not in portfolio: portfolio[item_name] = {"qty": 0, "total_buy": 0, "code": code}
        if action == "매수":
            portfolio[item_name]["qty"] += qty
            portfolio[item_name]["total_buy"] += qty * price
        elif action == "매도" and portfolio[item_name]["qty"] > 0:
            avg_p = portfolio[item_name]["total_buy"] / portfolio[item_name]["qty"]
            portfolio[item_name]["qty"] -= qty
            portfolio[item_name]["total_buy"] -= avg_p * qty

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 1️⃣ 메인 타이틀
st.title(f"📊 {selected_account}")

# 2️⃣ 실시간 종목 시세 (상단 카드 복구)
price_dict = {}
if active_stocks:
    st.subheader("💹 실시간 종목 시세")
    stock_html = '<div class="card-container">'
    total_eval = 0
    total_buy_sum = 0
    for name in active_stocks:
        live_p = get_live_price(portfolio[name]["code"])
        price_dict[name] = live_p
        total_eval += portfolio[name]["qty"] * live_p
        total_buy_sum += portfolio[name]["total_buy"]
        stock_html += f'<div class="custom-card"><div class="card-label">{name}</div><div class="card-value">{live_p:,}</div></div>'
    stock_html += '</div>'
    st.markdown(stock_html, unsafe_allow_html=True)

    total_asset = total_cash + total_eval

    # 3️⃣ 계좌 변동 및 요약 (구글 시트 히스토리 기준)
    st.divider()
    st.subheader("📈 계좌 변동 및 요약")
    
    df_history = load_sheet_data(HISTORY_GID)
    
    def get_comparison(days):
        if df_history.empty: return 0, 0.0
        h = df_history.copy()
        h['dt'] = h.iloc[:, 0].apply(parse_date_flexible)
        h = h.dropna(subset=['dt']).sort_values('dt', ascending=False)
        
        # 오늘 기록과 과거 기록 찾기
        today_val = total_asset # 실시간 기준
        target_dt = datetime.date.today() - datetime.timedelta(days=days)
        past_records = h[h['dt'] <= target_dt]
        
        if past_records.empty: return 0, 0.0
        
        row = past_records.iloc[0]
        if selected_account == "전체 계좌":
            past_val = (pd.to_numeric(str(row.iloc[1]).replace(',', ''), errors='coerce') or 0) + \
                       (pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0)
        else:
            col = 1 if selected_account == "기본 계좌" else 2
            past_val = pd.to_numeric(str(row.iloc[col]).replace(',', ''), errors='coerce') or 0
            
        diff = today_val - past_val
        rate = (diff / past_val * 100) if past_val != 0 else 0
        return diff, rate

    metrics_html = '<div class="card-container">'
    for label, d in [("전일대비", 1), ("전주대비", 7), ("전월대비", 30)]:
        v, r = get_comparison(d)
        cls = "up" if v > 0 else "down" if v < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(v):+,}</div><div class="card-delta {cls}">{r:+.2f}%</div></div>'
    
    t_profit_amt = total_eval - total_buy_sum
    t_profit_rate = (t_profit_amt / total_buy_sum * 100) if total_buy_sum > 0 else 0
    
    summary = [("💰 예수금", total_cash, ""), ("🏦 총자산", total_asset, ""), ("📊 총수익률", t_profit_amt, f"{t_profit_rate:+.2f}%")]
    for label, val, rs in summary:
        cls = "up" if "수익률" in label and val > 0 else "down" if "수익률" in label and val < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(val):,}</div><div class="card-delta {cls}">{rs}</div></div>'
    st.markdown(metrics_html + '</div>', unsafe_allow_html=True)

    # 4️⃣ 보유 종목 리스트
    st.divider()
    st.subheader("📋 보유 종목 리스트")
    res = []
    for n in active_stocks:
        cur_p = price_dict.get(n, 0)
        buy_avg = portfolio[n]["total_buy"] / portfolio[n]["qty"]
        eval_amt = portfolio[n]["qty"] * cur_p
        p_rate = ((cur_p - buy_avg) / buy_avg * 100) if buy_avg > 0 else 0
        res.append([n, portfolio[n]["qty"], int(buy_avg), cur_p, int(eval_amt), p_rate, (eval_amt/total_asset*100)])
    
    res.append(["💰 예수금", None, None, None, int(total_cash), None, (total_cash/total_asset*100)])
    df_res = pd.DataFrame(res, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    st.dataframe(df_res.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
    }).map(lambda v: f'color: {"#e63946" if v > 0 else "#457b9d" if v < 0 else "#212529"}; font-weight: bold;' if isinstance(v, (int, float)) else '', subset=['수익률']), 
    use_container_width=True, hide_index=True)
else:
    st.info("보유 종목이 없습니다.")