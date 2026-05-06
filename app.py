import pandas as pd
import streamlit as st
import requests
import os
import json
import datetime
import re

# 💾 1. 데이터 및 스타일 설정
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

# 📂 3. 데이터 로드 및 전처리
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
HISTORY_GID = "144293082"

@st.cache_data(ttl=10)
def load_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str).fillna('')
    except: return pd.DataFrame()

selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))
portfolio, total_cash = {}, 0

# 시트에서 데이터 읽기 (수량 및 평단가 오차 방지)
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
        code = str(row.iloc[5]).strip() if len(row) > 5 else ""
        if item not in portfolio:
            portfolio[item] = {"qty": qty, "buy_amt": qty * val, "code": code}
        else: # 동일 종목 합산 로직
            portfolio[item]["qty"] += qty
            portfolio[item]["buy_amt"] += (qty * val)

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]
st.title(f"📊 {selected_account}")

# 💹 4. 실시간 시세 카드
price_dict = {n: get_live_price(portfolio[n]["code"]) for n in active_stocks}
if active_stocks:
    st.subheader("💹 실시간 종목 시세")
    stock_html = '<div class="card-container">'
    for name in active_stocks:
        stock_html += f'<div class="custom-card"><div class="card-label">{name}</div><div class="card-value">{price_dict[name]:,}</div></div>'
    st.markdown(stock_html + '</div>', unsafe_allow_html=True)

# 📊 5. 자산 계산 및 요약 (오차 해결 핵심)
total_eval = sum(portfolio[n]["qty"] * price_dict[n] for n in active_stocks)
total_buy = sum(portfolio[n]["buy_amt"] for n in active_stocks)
current_total_asset = total_cash + total_eval # 실시간 합산 총자산
total_profit = total_eval - total_buy
total_profit_rate = (total_profit / total_buy * 100) if total_buy > 0 else 0

# 📈 6. 계좌 변동 (전주, 전월 탭 복구)
st.divider()
st.subheader("📈 계좌 변동 및 요약")
df_h = load_data(HISTORY_GID)

def get_comparison(days):
    if df_h.empty: return 0, 0
    h = df_h.copy()
    h.iloc[:, 0] = h.iloc[:, 0].apply(lambda x: re.sub(r'[^0-9\.]', '', str(x)).strip('.'))
    
    today_val = datetime.date(2026, 5, 6)
    target_date = today_val - datetime.timedelta(days=days)
    
    # 날짜별 데이터 찾기
    def get_val_by_offset(d):
        target_str = d.strftime("%Y.%m.%d")
        row = h[h.iloc[:, 0].str.contains(target_str, na=False)].head(1)
        if row.empty: return 0
        if selected_account == "전체 계좌":
            return (pd.to_numeric(str(row.iloc[0, 1]).replace(',', ''), errors='coerce') or 0) + \
                   (pd.to_numeric(str(row.iloc[0, 2]).replace(',', ''), errors='coerce') or 0)
        col = 1 if selected_account == "기본 계좌" else 2
        return pd.to_numeric(str(row.iloc[0, col]).replace(',', ''), errors='coerce') or 0

    past_val = get_val_by_offset(target_date)
    if past_val == 0: return 0, 0
    diff = current_total_asset - past_val
    return diff, (diff/past_val*100)

metrics_html = '<div class="card-container">'
for label, days in [("전일대비", 1), ("전주대비", 7), ("전월대비", 30)]:
    v, r = get_comparison(days)
    cls = "up" if v > 0 else "down" if v < 0 else ""
    metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(v):+,}</div><div class="card-delta {cls}">{r:+.2f}%</div></div>'

# 요약 카드 (총수익, 총잔고, 수익률)
p_cls = "up" if total_profit > 0 else "down" if total_profit < 0 else ""
metrics_html += f'<div class="custom-card"><div class="card-label">💰 총수익</div><div class="card-value {p_cls}">{int(total_profit):+,}</div></div>'
metrics_html += f'<div class="custom-card"><div class="card-label">🏦 총잔고</div><div class="card-value">{int(current_total_asset):,}</div></div>'
metrics_html += f'<div class="custom-card"><div class="card-label">📈 수익률</div><div class="card-value {p_cls}">{total_profit_rate:+.2f}%</div></div>'
st.markdown(metrics_html + '</div>', unsafe_allow_html=True)

# 📋 7. 보유 종목 리스트
st.divider()
st.subheader("📋 보유 종목 리스트")
res = []
for n in active_stocks:
    cp, ba = price_dict[n], portfolio[n]["buy_amt"] / portfolio[n]["qty"]
    ev = portfolio[n]["qty"] * cp
    res.append([n, portfolio[n]["qty"], int(ba), cp, int(ev), ((cp-ba)/ba*100), (ev/current_total_asset*100)])
res.append(["💰 예수금", None, None, None, int(total_cash), None, (total_cash/current_total_asset*100)])

df_res = pd.DataFrame(res, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
st.dataframe(df_res.style.format({
    "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
}).map(lambda v: f'color: {"#e63946" if v > 0 else "#457b9d" if v < 0 else "#212529"}; font-weight: bold;' if isinstance(v, (int, float)) else '', subset=['수익률']), 
use_container_width=True, hide_index=True)