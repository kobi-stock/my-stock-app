import pandas as pd
import streamlit as st
import requests
import datetime
import re

# 📱 1. 화면 설정 및 스타일 (image_adea95.png 스타일 유지)
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

# 💹 2. 실시간 시세 엔진 (네이버 금융 API 연동)
@st.cache_data(ttl=5)
def get_live_price(code):
    if not code or pd.isna(code): return 0
    clean_code = ''.join(filter(str.isdigit, str(code))).zfill(6)
    if clean_code == "000000": return 0
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except: return 0

# 📂 3. 데이터 로드 설정
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
HISTORY_GID = "144293082" 

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try:
        df = pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
        return df.fillna('')
    except: return pd.DataFrame()

def parse_date_flexible(s):
    try:
        s = re.sub(r'[^0-9\.]', '', str(s)).strip('.')
        parts = s.split('.')
        return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except: return None

# 🔐 4. 데이터 통합 및 종목 계산
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))
portfolio, total_cash = {}, 0
df_history = load_sheet_data(HISTORY_GID)

for name, gid in TAB_INFO.items():
    if selected_account != "전체 계좌" and selected_account != name: continue
    df_acc = load_sheet_data(gid)
    if df_acc.empty: continue
    
    for _, row in df_acc.iterrows():
        # 열 개수 체크 및 종목명 유효성 확인
        if len(row) < 5: continue
        item_name = str(row.iloc[1]).strip()
        if not item_name or item_name in ["종목", "nan", "None"]: continue
        
        # 예수금 처리
        if "예수금" in item_name:
            cash_val = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
            total_cash += cash_val
            continue
            
        # 종목 정보 추출
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        buy_price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4]).strip()
        code = str(row.iloc[5]).strip() if len(row) > 5 else ""

        if item_name not in portfolio: 
            portfolio[item_name] = {"qty": 0, "buy_amt": 0, "code": code}
        
        if action == "매수":
            portfolio[item_name]["qty"] += qty
            portfolio[item_name]["buy_amt"] += qty * buy_price
        elif action == "매도" and portfolio[item_name]["qty"] > 0:
            avg_p = portfolio[item_name]["buy_amt"] / portfolio[item_name]["qty"]
            portfolio[item_name]["qty"] -= qty
            portfolio[item_name]["buy_amt"] -= avg_p * qty

# 수량이 남은 종목만 필터링
active_stocks = {n: d for n, d in portfolio.items() if d["qty"] > 0}

# 5️⃣ 화면 출력 및 요약
st.title(f"📊 {selected_account}")

if active_stocks or total_cash > 0:
    # 실시간 현재가 가져오기
    price_dict = {n: get_live_price(d["code"]) for n, d in active_stocks.items()}
    total_eval = sum(active_stocks[n]["qty"] * price_dict.get(n, 0) for n in active_stocks)
    total_asset = total_cash + total_eval

    # --- 📈 계좌 변동 요약 (image_adf4e0.png 기준 1,000만원 차이 반영) ---
    st.divider()
    st.subheader("📈 계좌 변동 및 요약")
    
    def get_comparison(days):
        if df_history.empty: return 0, 0.0
        h = df_history.copy()
        h['dt'] = h.iloc[:, 0].apply(parse_date_flexible)
        h = h.dropna(subset=['dt']).sort_values('dt', ascending=False)
        
        today_val = 0
        past_val = 0
        
        # 오늘 기록과 과거 기록 찾기
        today_row = h[h['dt'] == datetime.date(2026, 5, 6)] # 오늘 날짜 강제 지정 또는 datetime.date.today()
        past_date = datetime.date(2026, 5, 6) - datetime.timedelta(days=days)
        past_row = h[h['dt'] <= past_date].head(1)
        
        def calc_sum(row):
            if row.empty: return 0
            if selected_account == "전체 계좌":
                return (pd.to_numeric(str(row.iloc[0, 1]).replace(',', ''), errors='coerce') or 0) + \
                       (pd.to_numeric(str(row.iloc[0, 2]).replace(',', ''), errors='coerce') or 0)
            col = 1 if selected_account == "기본 계좌" else 2
            return pd.to_numeric(str(row.iloc[0, col]).replace(',', ''), errors='coerce') or 0

        today_val = calc_sum(today_row)
        past_val = calc_sum(past_row)
        
        diff = today_val - past_val
        rate = (diff / past_val * 100) if past_val != 0 else 0
        return diff, rate

    # 카드형 지표 출력
    metrics_html = '<div class="card-container">'
    for label, d in [("전일대비", 1), ("전주대비", 7), ("전월대비", 30)]:
        v, r = get_comparison(d)
        cls = "up" if v > 0 else "down" if v < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(v):+,}</div><div class="card-delta {cls}">{r:+.2f}%</div></div>'
    
    # 총자산 정보 추가
    metrics_html += f'<div class="custom-card"><div class="card-label">💰 예수금</div><div class="card-value">{int(total_cash):,}</div></div>'
    metrics_html += f'<div class="custom-card"><div class="card-label">🏦 현재 총자산</div><div class="card-value">{int(total_asset):,}</div></div>'
    st.markdown(metrics_html + '</div>', unsafe_allow_html=True)

    # --- 📋 보유 종목 리스트 (현재가 복구) ---
    st.divider()
    st.subheader("📋 보유 종목 리스트")
    
    res = []
    for n, d in active_stocks.items():
        cur_p = price_dict.get(n, 0)
        buy_avg = d["buy_amt"] / d["qty"]
        eval_amt = d["qty"] * cur_p
        profit_rate = ((cur_p - buy_avg) / buy_avg * 100) if buy_avg > 0 else 0
        res.append([n, d["qty"], int(buy_avg), cur_p, int(eval_amt), profit_rate])
    
    df_res = pd.DataFrame(res, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률"])
    st.dataframe(df_res.style.format({
        "수량": "{:,.0f}", "평단": "{:,.0f}", "현재가": "{:,.0f}", "평가액": "{:,.0f}", "수익률": "{:+.2f}%"
    }).map(lambda v: f'color: {"#e63946" if v > 0 else "#457b9d" if v < 0 else "#212529"}; font-weight: bold;' if isinstance(v, (int, float)) else '', subset=['수익률']), 
    use_container_width=True, hide_index=True)

else:
    st.info("현재 보유 중인 종목이 없거나 데이터를 불러올 수 없습니다.")