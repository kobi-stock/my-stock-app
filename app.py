import pandas as pd
import streamlit as st
import requests
import os
import json
import datetime
import re

# 💾 1. 데이터 관리 (로컬 캐시 및 설정 저장)
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

# 💹 2. 실시간 시세 엔진 (네이버 금융 API 활용)
@st.cache_data(ttl=5)
def get_live_price(code):
    if not code or pd.isna(code): return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except:
        return 0

# 📱 3. 화면 설정 및 세련된 스타일링
st.set_page_config(page_title="주식 포트폴리오", layout="centered")

st.markdown("""
<style>
    h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
    h3 { font-size: 1.1rem !important; margin-top: 1rem !important; }
    .card-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 15px; }
    .custom-card {
        background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px;
        padding: 10px; min-width: 105px; flex: 1 1 calc(30% - 8px);
        box-shadow: 1px 1px 3px rgba(0,0,0,0.05); text-align: center;
    }
    @media (max-width: 480px) { .custom-card { flex: 1 1 calc(48% - 8px); } }
    .card-label { font-size: 0.75rem; color: #6c757d; margin-bottom: 4px; }
    .card-value { font-size: 0.95rem; font-weight: 700; color: #212529; }
    .card-delta { font-size: 0.75rem; font-weight: 600; margin-top: 2px; }
    .up { color: #e63946 !important; }
    .down { color: #457b9d !important; }
</style>
""", unsafe_allow_html=True)

# 📂 4. 데이터 소스 (구글 스프레드시트 연동)
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
HISTORY_GID = "144293082" # 히스토리 탭 GID

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str).fillna('')
    except: return pd.DataFrame()

def parse_date_korea(s):
    try:
        s = re.sub(r'[^0-9\.]', '', str(s)).strip('.')
        p = s.split('.')
        return datetime.date(int(p[0]), int(p[1]), int(p[2]))
    except: return None

# 사이드바 설정
st.sidebar.title("🔐 계좌 설정")
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

# 데이터 통합 프로세스
portfolio, total_cash = {}, 0
for name, gid in TAB_INFO.items():
    if selected_account != "전체 계좌" and selected_account != name: continue
    df_acc = load_sheet_data(gid)
    if df_acc.empty: continue
    for _, row in df_acc.iterrows():
        item = str(row.iloc[1]).strip()
        if not item or item in ["종목", "nan"]: continue
        
        # '예수금' 단어 포함 시 단가(C열) 혹은 평가액(D열)에서 합산
        val = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        if "예수금" in item:
            total_cash += val
            continue
            
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        code = str(row.iloc[5]).strip() if len(row) > 5 else ""
        if item not in portfolio: portfolio[item] = {"qty": qty, "buy_amt": qty * val, "code": code}

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]
st.title(f"📊 {selected_account}")

# 1️⃣ 상단 실시간 종목 시세 카드
if active_stocks:
    st.subheader("💹 실시간 종목 시세")
    price_dict = {n: get_live_price(portfolio[n]["code"]) for n in active_stocks}
    stock_html = '<div class="card-container">'
    for name in active_stocks:
        stock_html += f'<div class="custom-card"><div class="card-label">{name}</div><div class="card-value">{price_dict[name]:,}</div></div>'
    st.markdown(stock_html + '</div>', unsafe_allow_html=True)

    # 2️⃣ 계좌 변동 및 요약 (구글 시트 기록 기준)
    st.divider()
    st.subheader("📈 계좌 변동 및 요약")
    df_h = load_sheet_data(HISTORY_GID)

    def get_history_val(days):
        if df_h.empty: return 0, 0, 0
        h = df_h.copy()
        h['dt'] = h.iloc[:, 0].apply(parse_date_korea)
        h = h.dropna(subset=['dt']).sort_values('dt', ascending=False)
        
        # 기준일(오늘)과 과거일 데이터 추출
        today_val = datetime.date(2026, 5, 6) # 시스템 기준 오늘
        today_row = h[h['dt'] == today_val]
        past_date = today_val - datetime.timedelta(days=days)
        past_row = h[h['dt'] <= past_date].head(1)
        
        if today_row.empty or past_row.empty: return 0, 0, 0
        
        def extract(row):
            if selected_account == "전체 계좌":
                return (pd.to_numeric(str(row.iloc[0, 1]).replace(',', ''), errors='coerce') or 0) + \
                       (pd.to_numeric(str(row.iloc[0, 2]).replace(',', ''), errors='coerce') or 0)
            col = 1 if selected_account == "기본 계좌" else 2
            return pd.to_numeric(str(row.iloc[0, col]).replace(',', ''), errors='coerce') or 0

        curr, prev = extract(today_row), extract(past_row)
        diff = curr - prev
        return diff, (diff/prev*100) if prev != 0 else 0, curr

    # 지표 계산
    d_v, d_r, current_total_sheet = get_history_val(1)
    w_v, w_r, _ = get_history_val(7)
    m_v, m_r, _ = get_history_val(30)

    # 실시간 기반 수익 계산
    total_eval = sum(portfolio[n]["qty"] * price_dict[n] for n in active_stocks)
    total_buy = sum(portfolio[n]["buy_amt"] for n in active_stocks)
    total_profit = total_eval - total_buy
    total_profit_rate = (total_profit / total_buy * 100) if total_buy > 0 else 0

    # 카드 출력 (2행 구성)
    summary_html = '<div class="card-container">'
    # 1행: 기간별 변동 (전일대비 1,000만 원 표시 등)
    for label, v, r in [("전일대비", d_v, d_r), ("전주대비", w_v, w_r), ("전월대비", m_v, m_r)]:
        cls = "up" if v > 0 else "down" if v < 0 else ""
        summary_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(v):+,}</div><div class="card-delta {cls}">{r:+.2f}%</div></div>'
    # 2행: 핵심 요약
    p_cls = "up" if total_profit > 0 else "down" if total_profit < 0 else ""
    summary_html += f'<div class="custom-card"><div class="card-label">💰 총수익</div><div class="card-value {p_cls}">{int(total_profit):+,}</div></div>'
    summary_html += f'<div class="custom-card"><div class="card-label">🏦 총잔고(시트)</div><div class="card-value">{int(current_total_sheet):,}</div></div>'
    summary_html += f'<div class="custom-card"><div class="card-label">📈 수익률</div><div class="card-value {p_cls}">{total_profit_rate:+.2f}%</div></div>'
    st.markdown(summary_html + '</div>', unsafe_allow_html=True)

    # 3️⃣ 보유 종목 리스트 (예수금 비중 포함)
    st.divider()
    st.subheader("📋 보유 종목 리스트")
    res_data = []
    total_asset_real = total_cash + total_eval
    for n in active_stocks:
        cp, ba = price_dict[n], portfolio[n]["buy_amt"] / portfolio[n]["qty"]
        ev = portfolio[n]["qty"] * cp
        res_data.append([n, portfolio[n]["qty"], int(ba), cp, int(ev), ((cp-ba)/ba*100), (ev/total_asset_real*100)])

    # 예수금 행 추가
    res_data.append(["💰 예수금", None, None, None, int(total_cash), None, (total_cash/total_asset_real*100)])

    df_final = pd.DataFrame(res_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    st.dataframe(df_final.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
    }).map(lambda v: f'color: {"#e63946" if v > 0 else "#457b9d" if v < 0 else "#212529"}; font-weight: bold;' if isinstance(v, (int, float)) else '', subset=['수익률']), 
    use_container_width=True, hide_index=True)

else:
    st.info("데이터를 불러올 수 없거나 보유 종목이 없습니다.")