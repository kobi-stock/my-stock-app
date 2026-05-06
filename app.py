import pandas as pd
import streamlit as st
import requests
import datetime
import re

# 📱 1. 화면 설정 및 스타일
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

# 💹 2. 실시간 시세 엔진
@st.cache_data(ttl=5)
def get_live_price(code):
    if not code or pd.isna(code) or str(code).strip() == "" or code == "None": return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except: return 0

# 📂 3. 데이터 로드 설정 (GID 확인 필수)
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
HISTORY_GID = "144293082" # ← 실제 히스토리 탭 GID로 수정하세요.

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try:
        df = pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
        return df.fillna('')
    except: return pd.DataFrame()

# 날짜 파싱 유틸리티 (마침표 대응)
def parse_date_flexible(s):
    try:
        s = re.sub(r'[^0-9\.]', '', str(s)).strip('.')
        parts = s.split('.')
        if len(parts) == 3:
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        return pd.to_datetime(s).date()
    except: return None

# 🔐 계좌 선택 및 데이터 통합
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

portfolio, total_cash = {}, 0
df_history = load_sheet_data(HISTORY_GID)

# 개별 탭 처리
for name, gid in TAB_INFO.items():
    if selected_account != "전체 계좌" and selected_account != name: continue
    
    df_acc = load_sheet_data(gid)
    if df_acc.empty: continue
    
    tab_cash = 0
    for _, row in df_acc.iterrows():
        item_name = str(row.iloc[1]).strip()
        code = str(row.iloc[5]).strip()
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4]).strip()

        if "예수금" in item_name:
            tab_cash = price
            continue
        if not item_name or item_name == "종목": continue

        if item_name not in portfolio: portfolio[item_name] = {"qty": 0, "buy_amt": 0, "code": code}
        if action == "매수":
            portfolio[item_name]["qty"] += qty
            portfolio[item_name]["buy_amt"] += qty * price
        elif action == "매도" and portfolio[item_name]["qty"] > 0:
            avg_p = portfolio[item_name]["buy_amt"] / portfolio[item_name]["qty"]
            portfolio[item_name]["qty"] -= qty
            portfolio[item_name]["buy_amt"] -= avg_p * qty
    total_cash += tab_cash

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 4️⃣ 메인 화면
st.title(f"📊 {selected_account}")

if active_stocks or total_cash > 0:
    price_dict = {n: get_live_price(portfolio[n]["code"]) for n in active_stocks}
    total_eval = sum(portfolio[n]["qty"] * price_dict.get(n, 0) for n in active_stocks)
    total_buy_sum = sum(portfolio[n]["buy_amt"] for n in active_stocks)
    total_asset = total_cash + total_eval

    # 📈 계좌 변동 계산 (강화된 로직)
    st.divider()
    st.subheader("📈 계좌 변동 및 요약")
    
    def get_comparison(days):
        if df_history.empty: return 0, 0.0
        
        # 히스토리 날짜 파싱 및 정렬
        h = df_history.copy()
        h['dt'] = h.iloc[:, 0].apply(parse_date_flexible)
        h = h.dropna(subset=['dt']).sort_values('dt', ascending=False)
        
        today = datetime.date.today()
        target_dt = today - datetime.timedelta(days=days)
        
        # 오늘보다 과거인 데이터 중 가장 최신 것 선택
        past = h[h['dt'] <= target_dt]
        if past.empty: return 0, 0.0
        
        row = past.iloc[0]
        if selected_account == "전체 계좌":
            v_b = pd.to_numeric(str(row.iloc[1]).replace(',', ''), errors='coerce') or 0
            v_h = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
            past_val = v_b + v_h
        elif selected_account == "기본 계좌":
            past_val = pd.to_numeric(str(row.iloc[1]).replace(',', ''), errors='coerce') or 0
        else:
            past_val = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
            
        diff = total_asset - past_val
        return diff, (diff / past_val * 100) if past_val != 0 else 0

    metrics_html = '<div class="card-container">'
    for label, d in [("전일대비", 1), ("전주대비", 7), ("전월대비", 30)]:
        v, r = get_comparison(d)
        cls = "up" if v > 0 else "down" if v < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(v):+,}</div><div class="card-delta {cls}">{r:+.2f}%</div></div>'
    
    t_profit = total_eval - total_buy_sum
    t_rate = (t_profit / total_buy_sum * 100) if total_buy_sum > 0 else 0
    for l, v, rs in [("💰 예수금", total_cash, ""), ("🏦 총자산", total_asset, ""), ("📊 총수익률", t_profit, f"{t_rate:+.2f}%")]:
        cls = "up" if "수익률" in l and v > 0 else "down" if "수익률" in l and v < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{l}</div><div class="card-value">{int(v):,}</div><div class="card-delta {cls}">{rs}</div></div>'
    st.markdown(metrics_html + '</div>', unsafe_allow_html=True)

    # 📋 보유 종목 리스트 (필요시 추가)