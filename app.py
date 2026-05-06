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
        padding: 10px; min-width: 100px; flex: 1 1 calc(33.3% - 8px);
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

# 📂 3. 구글 시트 데이터 로드 설정
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
HISTORY_GID = "여기에_히스토리_탭_GID_입력" 

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
    except: return pd.DataFrame()

# 🔐 사이드바 설정
st.sidebar.title("🔐 계좌 설정")
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

# [데이터 로드]
all_dfs = []
if selected_account == "전체 계좌":
    for gid in TAB_INFO.values(): all_dfs.append(load_sheet_data(gid))
else:
    all_dfs.append(load_sheet_data(TAB_INFO[selected_account]))

df_raw = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
df_history = load_sheet_data(HISTORY_GID)

# [주식 및 예수금 처리]
portfolio = {}
cash_list = []

if not df_raw.empty:
    for _, row in df_raw.iterrows():
        name = str(row.iloc[1]).strip()
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4]).strip()
        code = str(row.iloc[5]).strip()

        if not name or name == "nan" or name == "종목": continue
        if "예수금" in name:
            cash_list.append(price)
            continue

        if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * price
        elif action == "매도" and portfolio[name]["qty"] > 0:
            avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
            portfolio[name]["qty"] -= qty
            portfolio[name]["total_buy"] -= avg_p * qty

total_cash = sum(cash_list) if selected_account == "전체 계좌" else (cash_list[-1] if cash_list else 0)
active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 4️⃣ 메인 화면 출력
st.title(f"📊 {selected_account}")

if active_stocks or total_cash > 0:
    price_dict = {}
    if active_stocks:
        st.subheader("💹 실시간 종목 시세")
        stock_html = '<div class="card-container">'
        for name in active_stocks:
            live_p = get_live_price(portfolio[name]["code"])
            price_dict[name] = live_p
            stock_html += f'<div class="custom-card"><div class="card-label">{name}</div><div class="card-value">{live_p:,}</div></div>'
        stock_html += '</div>'
        st.markdown(stock_html, unsafe_allow_html=True)

    total_eval = sum(portfolio[name]["qty"] * price_dict.get(name, 0) for name in active_stocks)
    total_buy_sum = sum(portfolio[name]["total_buy"] for name in active_stocks)
    total_asset = total_cash + total_eval

    # 5️⃣ 계좌 변동 및 요약 (확장된 히스토리 시트 대응)
    st.divider()
    st.subheader("📈 계좌 변동 및 요약")
    
    def get_comparison(days):
        if df_history.empty: return 0, 0.0
        target_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        past_rows = df_history[df_history.iloc[:, 0] <= target_date].sort_values(by=df_history.columns[0], ascending=False)
        if past_rows.empty: return 0, 0.0
        
        # 선택된 계좌에 따라 열(Column) 선택
        # B열: 기본계좌, C열: 한투계좌
        if selected_account == "전체 계좌":
            val_b = pd.to_numeric(str(past_rows.iloc[0, 1]).replace(',', ''), errors='coerce') or 0
            val_c = pd.to_numeric(str(past_rows.iloc[0, 2]).replace(',', ''), errors='coerce') or 0
            past_val = val_b + val_c
        elif selected_account == "기본 계좌":
            past_val = pd.to_numeric(str(past_rows.iloc[0, 1]).replace(',', ''), errors='coerce') or 0
        else: # 한국투자증권
            past_val = pd.to_numeric(str(past_rows.iloc[0, 2]).replace(',', ''), errors='coerce') or 0
            
        diff = total_asset - past_val
        return diff, (diff / past_val * 100) if past_val != 0 else 0

    d_val, d_rate = get_comparison(1)
    w_val, w_rate = get_comparison(7)
    t_profit_amt = total_eval - total_buy_sum
    t_profit_rate = (t_profit_amt / total_buy_sum * 100) if total_buy_sum > 0 else 0

    metrics_html = '<div class="card-container">'
    for label, val, rate in [("전일대비", d_val, d_rate), ("전주대비", w_val, w_rate)]:
        cls = "up" if val > 0 else "down" if val < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(val):+,}</div><div class="card-delta {cls}">{rate:+.2f}%</div></div>'
    
    summary = [("💰 예수금", total_cash, ""), ("🏦 총자산", total_asset, ""), ("📊 총수익률", t_profit_amt, f"{t_profit_rate:+.2f}%")]
    for label, val, rate_str in summary:
        cls = "up" if "수익률" in label and val > 0 else "down" if "수익률" in label and val < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(val):,}</div><div class="card-delta {cls}">{rate_str}</div></div>'
    metrics_html += '</div>'
    st.markdown(metrics_html, unsafe_allow_html=True)

    # 6️⃣ 보유 종목 리스트 (스타일 유지)
    st.divider()
    st.subheader("📋 보유 종목 리스트")
    result_list = []
    for name in active_stocks:
        d = portfolio[name]
        curr_p = price_dict.get(name, 0)
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        result_list.append([name, d["qty"], int(avg_p), int(curr_p), int(eval_amt), round(profit_r, 2), round(eval_amt/total_asset*100, 1)])
    
    result_list.append(["💰 예수금", None, None, None, int(total_cash), None, round(total_cash/total_asset*100, 1)])
    df_final = pd.DataFrame(result_list, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    st.dataframe(df_final.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
    }).map(lambda v: f'color: {"#e63946" if v > 0 else "#457b9d" if v < 0 else "#212529"}; font-weight: bold;' if isinstance(v, (int, float)) else '', subset=['수익률']), use_container_width=True, hide_index=True)