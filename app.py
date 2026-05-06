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
        padding: 10px; min-width: 100px; flex: 1 1 calc(25% - 8px);
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

# 📂 3. 구글 시트 로드 (gid 설정 확인 필수)
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
HISTORY_GID = "여기에_히스토리_탭_GID_입력" 

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try:
        df = pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
        return df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    except: return pd.DataFrame()

# 🔐 사이드바 및 데이터 로드
st.sidebar.title("🔐 계좌 설정")
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

all_dfs = []
if selected_account == "전체 계좌":
    for gid in TAB_INFO.values(): all_dfs.append(load_sheet_data(gid))
else:
    all_dfs.append(load_sheet_data(TAB_INFO[selected_account]))

df_raw = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
df_history = load_sheet_data(HISTORY_GID)

# [히스토리 날짜 전처리]
if not df_history.empty:
    df_history.iloc[:, 0] = pd.to_datetime(df_history.iloc[:, 0]).dt.strftime('%Y-%m-%d')

# [포트폴리오 계산]
portfolio, cash_list = {}, []
if not df_raw.empty:
    for _, row in df_raw.iterrows():
        name, code = str(row.iloc[1]), str(row.iloc[5])
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4])

        if not name or name == "nan" or name == "종목": continue
        if "예수금" in name:
            cash_list.append(price)
            continue

        if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * price
        elif action == "매도":
            avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"] if portfolio[name]["qty"] > 0 else 0
            portfolio[name]["qty"] -= qty
            portfolio[name]["total_buy"] -= avg_p * qty

total_cash = sum(cash_list) if selected_account == "전체 계좌" else (cash_list[-1] if cash_list else 0)
active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 4️⃣ 메인 출력
st.title(f"📊 {selected_account}")

if active_stocks or total_cash > 0:
    price_dict = {name: get_live_price(portfolio[name]["code"]) for name in active_stocks}
    total_eval = sum(portfolio[name]["qty"] * price_dict.get(name, 0) for name in active_stocks)
    total_buy_sum = sum(portfolio[name]["total_buy"] for name in active_stocks)
    total_asset = total_cash + total_eval

    # 📈 계좌 변동 및 요약 (전일/전주/전월)
    st.divider()
    st.subheader("📈 계좌 변동 및 요약")
    
    def get_comparison(days):
        if df_history.empty: return 0, 0.0
        # 기준 날짜 계산
        target_date = (datetime.date.today() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        # 기준 날짜보다 같거나 작은(과거) 데이터 중 가장 최근 것 선택
        past_rows = df_history[df_history.iloc[:, 0] <= target_date].sort_values(by=df_history.columns[0], ascending=False)
        
        if past_rows.empty: return 0, 0.0
        
        if selected_account == "전체 계좌":
            val_b = pd.to_numeric(str(past_rows.iloc[0, 1]).replace(',', ''), errors='coerce') or 0
            val_c = pd.to_numeric(str(past_rows.iloc[0, 2]).replace(',', ''), errors='coerce') or 0
            past_val = val_b + val_c
        elif selected_account == "기본 계좌":
            past_val = pd.to_numeric(str(past_rows.iloc[0, 1]).replace(',', ''), errors='coerce') or 0
        else: # 한국투자증권
            past_val = pd.to_numeric(str(past_rows.iloc[0, 2]).replace(',', ''), errors='coerce') or 0
            
        diff = total_asset - past_val
        rate = (diff / past_val * 100) if past_val != 0 else 0
        return diff, rate

    # 변동 데이터 호출
    comps = [("전일대비", 1), ("전주대비", 7), ("전월대비", 30)]
    
    metrics_html = '<div class="card-container">'
    for label, days in comps:
        val, rate = get_comparison(days)
        cls = "up" if val > 0 else "down" if val < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(val):+,}</div><div class="card-delta {cls}">{rate:+.2f}%</div></div>'
    
    # 총자산 정보 등 추가 카드
    t_profit_amt = total_eval - total_buy_sum
    t_profit_rate = (t_profit_amt / total_buy_sum * 100) if total_buy_sum > 0 else 0
    
    summary_items = [("💰 예수금", total_cash, ""), ("🏦 총자산", total_asset, ""), ("📊 총수익률", t_profit_amt, f"{t_profit_rate:+.2f}%")]
    for label, val, rate_str in summary_items:
        cls = "up" if "수익률" in label and val > 0 else "down" if "수익률" in label and val < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(val):,}</div><div class="card-delta {cls}">{rate_str}</div></div>'
    
    metrics_html += '</div>'
    st.markdown(metrics_html, unsafe_allow_html=True)

    # 📋 보유 종목 리스트 (생략 없이 유지)
    st.divider()
    st.subheader("📋 보유 종목 리스트")
    res_list = [[n, portfolio[n]["qty"], int(portfolio[n]["total_buy"]/portfolio[n]["qty"]), price_dict[n], portfolio[n]["qty"]*price_dict[n], round((price_dict[n]-(portfolio[n]["total_buy"]/portfolio[n]["qty"]))/(portfolio[n]["total_buy"]/portfolio[n]["qty"])*100,2), round((portfolio[n]["qty"]*price_dict[n])/total_asset*100,1)] for n in active_stocks]
    res_list.append(["💰 예수금", None, None, None, int(total_cash), None, round(total_cash/total_asset*100, 1)])
    
    df_f = pd.DataFrame(res_list, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    st.dataframe(df_f.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
    }).map(lambda v: f'color: {"#e63946" if v > 0 else "#457b9d" if v < 0 else "#212529"}; font-weight: bold;' if isinstance(v, (int, float)) else '', subset=['수익률']), use_container_width=True, hide_index=True)
else:
    st.info("시트에 데이터를 입력해주세요.")