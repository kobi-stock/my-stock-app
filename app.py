import pandas as pd
import streamlit as st
import requests
import os
import datetime
import re

# 💾 1. 화면 설정
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
st.markdown("""
<style>
    h1 { font-size: 1.5rem !important; }
    .card-container { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px; }
    .custom-card {
        background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px;
        padding: 10px; min-width: 100px; flex: 1 1 calc(30% - 8px);
        box-shadow: 1px 1px 3px rgba(0,0,0,0.05); text-align: center;
    }
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
    if not code or pd.isna(code): return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except: return 0

# 📂 3. 데이터 로드 및 정밀 계산
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
HISTORY_GID = "144293082"

@st.cache_data(ttl=10)
def load_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str).fillna('')
    except: return pd.DataFrame()

selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))
portfolio, total_cash = {}, 0

for name, gid in TAB_INFO.items():
    if selected_account != "전체 계좌" and selected_account != name: continue
    df_acc = load_data(gid)
    for _, row in df_acc.iterrows():
        item = str(row.iloc[1]).strip()
        if not item or item in ["종목", "nan"]: continue
        
        val = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        if "예수금" in item:
            total_cash += val
            continue
            
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4]).strip()
        code = str(row.iloc[5]).strip() if len(row) > 5 else ""
        
        if item not in portfolio:
            portfolio[item] = {"qty": 0, "total_buy_cost": 0, "code": code}
        
        if action == "매수":
            portfolio[item]["qty"] += qty
            portfolio[item]["total_buy_cost"] += (qty * val)
        elif action == "매도":
            if portfolio[item]["qty"] > 0:
                # 매도 시 평단가 기준으로 매수 원가를 차감하여 '보유 종목 원가'만 남김
                unit_cost = portfolio[item]["total_buy_cost"] / portfolio[item]["qty"]
                portfolio[item]["qty"] -= qty
                portfolio[item]["total_buy_cost"] -= (qty * unit_cost)

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]
st.title(f"📊 {selected_account}")

# 💹 4. 실시간 시세 및 자산 계산
price_dict = {n: get_live_price(portfolio[n]["code"]) for n in active_stocks}

# 핵심 계산 공식
total_eval_amt = sum(portfolio[n]["qty"] * price_dict[n] for n in active_stocks) # 총평가액
total_buy_cost_sum = sum(portfolio[n]["total_buy_cost"] for n in active_stocks) # 총매수액(원가)
current_total_asset = total_cash + total_eval_amt # 총잔고 (예수금 + 평가액)

# 총수익 = 총잔고 - (매수원가 + 예수금) 이 아니라, 
# 현재 보유 종목에서 발생하는 실시간 수익으로 정의하여 항등식 유지
total_profit_val = total_eval_amt - total_buy_cost_sum
total_profit_pct = (total_profit_val / total_buy_cost_sum * 100) if total_buy_cost_sum > 0 else 0

# 📈 5. 계좌 변동 요약 (전일/전주/전월 복구)
st.divider()
st.subheader("📈 계좌 변동 및 요약")
df_h = load_data(HISTORY_GID)

def get_comparison(days):
    if df_h.empty: return 0, 0
    h = df_h.copy()
    h.iloc[:, 0] = h.iloc[:, 0].apply(lambda x: re.sub(r'[^0-9\.]', '', str(x)).strip('.'))
    # 시스템 기준 오늘 날짜 (2026.05.06) 사용
    today_val = datetime.date(2026, 5, 6)
    target_date = today_val - datetime.timedelta(days=days)
    target_str = target_date.strftime("%Y.%m.%d")
    
    row = h[h.iloc[:, 0].str.contains(target_str, na=False)].head(1)
    if row.empty: return 0, 0
    
    if selected_account == "전체 계좌":
        past_val = (pd.to_numeric(str(row.iloc[1]).replace(',', ''), errors='coerce') or 0) + \
                   (pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0)
    else:
        col = 1 if selected_account == "기본 계좌" else 2
        past_val = pd.to_numeric(str(row.iloc[col]).replace(',', ''), errors='coerce') or 0
        
    if past_val == 0: return 0, 0
    diff = current_total_asset - past_val
    return diff, (diff/past_val*100)

metrics_html = '<div class="card-container">'
for label, days in [("전일대비", 1), ("전주대비", 7), ("전월대비", 30)]:
    v, r = get_comparison(days)
    cls = "up" if v > 0 else "down" if v < 0 else ""
    metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(v):+,}</div><div class="card-delta {cls}">{r:+.2f}%</div></div>'

p_cls = "up" if total_profit_val > 0 else "down" if total_profit_val < 0 else ""
metrics_html += f'<div class="custom-card"><div class="card-label">📥 총매수액</div><div class="card-value">{int(total_buy_cost_sum):,}</div></div>'
metrics_html += f'<div class="custom-card"><div class="card-label">💰 총수익</div><div class="card-value {p_cls}">{int(total_profit_val):+,}</div></div>'
metrics_html += f'<div class="custom-card"><div class="card-label">🏦 총잔고</div><div class="card-value">{int(current_total_asset):,}</div></div>'
st.markdown(metrics_html + '</div>', unsafe_allow_html=True)

# 📋 6. 보유 종목 리스트
st.divider()
st.subheader("📋 보유 종목 리스트")
res_list = []
for n in active_stocks:
    cp = price_dict[n]
    qty = portfolio[n]["qty"]
    ba = portfolio[n]["total_buy_cost"] / qty
    ev = qty * cp
    res_list.append([n, qty, int(ba), cp, int(ev), ((cp-ba)/ba*100), (ev/current_total_asset*100)])
res_list.append(["💰 예수금", None, None, None, int(total_cash), None, (total_cash/current_total_asset*100)])

df_res = pd.DataFrame(res_list, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
st.dataframe(df_res.style.format({
    "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
}).map(lambda v: f'color: {"#e63946" if v > 0 else "#457b9d" if v < 0 else "#212529"}; font-weight: bold;' if isinstance(v, (int, float)) else '', subset=['수익률']), 
use_container_width=True, hide_index=True)