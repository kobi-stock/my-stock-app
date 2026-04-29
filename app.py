import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json

# -------------------------------
# 💾 예수금 영구 저장 기능
# -------------------------------
CASH_FILE = "cash_data.json"

def load_cash_data():
    if os.path.exists(CASH_FILE):
        with open(CASH_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cash_data(account_name, amount):
    data = load_cash_data()
    data[account_name] = amount
    with open(CASH_FILE, "w") as f:
        json.dump(data, f)

# -------------------------------
# 📱 화면 구성 및 스타일 설정
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오 관리")
st.markdown("""
<style>
.main .block-container {
    max-width: 900px;
    padding-top: 2rem;
}
div.stNumberInput > label { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# 📂 계좌 선택 및 데이터 로드
# -------------------------------
st.sidebar.title("📂 계좌 관리")
file_options = {
    "기본 계좌": "trade_log.xlsx",
    "한국투자증권": "trade_log_한투.xlsx"
}
existing_files = {name: path for name, path in file_options.items() if os.path.exists(path)}

if not existing_files:
    st.error("❗ 엑셀 파일(trade_log.xlsx)이 존재하지 않습니다.")
    st.stop()

selected_account = st.sidebar.selectbox("계좌를 선택하세요", ["전체 계좌"] + list(existing_files.keys()))

if selected_account == "전체 계좌":
    df = pd.concat([pd.read_excel(p) for p in existing_files.values()], ignore_index=True)
else:
    df = pd.read_excel(existing_files[selected_account])

st.title(f"📊 {selected_account} 포트폴리오")

# -------------------------------
# 💰 예수금 처리
# -------------------------------
cash_data = load_cash_data()

if selected_account == "전체 계좌":
    total_saved_cash = sum([cash_data.get(acc, 1000000) for acc in existing_files.keys()])
    cash = total_saved_cash
    st.info(f"💡 전체 계좌의 예수금은 각 개별 계좌 설정값의 합계({cash:,}원)입니다.")
else:
    saved_val = cash_data.get(selected_account, 1000000)
    cash_input = st.number_input(f"💰 {selected_account} 예수금 설정", value=saved_val, step=10000)
    if cash_input != saved_val:
        save_cash_data(selected_account, cash_input)
    cash = cash_input

# -------------------------------
# 🔹 시세 데이터 처리
# -------------------------------
code_map = {row["종목"]: str(row["코드"]).zfill(6) for _, row in df.iterrows()}

@st.cache_data(ttl=60)
def get_price(code):
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={code}"
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        price = soup.select_one(".no_today .blind").text
        return int(price.replace(",", ""))
    except:
        return 0

# -------------------------------
# 📊 포트폴리오 계산
# -------------------------------
portfolio = {}
for _, row in df.iterrows():
    name, qty, price, action = row["종목"], row["수량"], row["가격"], row["구분"]
    if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0}
    if action == "매수":
        portfolio[name]["qty"] += qty
        portfolio[name]["total_buy"] += qty * price
    elif action == "매도":
        if portfolio[name]["qty"] > 0:
            avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
            portfolio[name]["qty"] -= qty
            portfolio[name]["total_buy"] -= avg_p * qty
        if portfolio[name]["qty"] <= 0:
            portfolio[name]["qty"] = 0; portfolio[name]["total_buy"] = 0

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 현재가 입력창
st.markdown("### 💹 실시간 시세")
price_dict = {}
if active_stocks:
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
        auto_p = get_price(code_map.get(name, "000000"))
        with cols[i % 4]:
            price_dict[name] = st.number_input(name, value=int(auto_p) if auto_p > 0 else int(avg_p), key=f"p_{selected_account}_{name}")

# 결과 데이터 집계
result_list = []
total_eval, total_buy = 0, 0
for name in active_stocks:
    d = portfolio[name]
    avg_p = d["total_buy"] / d["qty"]
    curr_p = price_dict[name]
    eval_amt = d["qty"] * curr_p
    total_eval += eval_amt
    total_buy += d["total_buy"]
    profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
    result_list.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])

total_asset = cash + total_eval
total_profit_amt = total_eval - total_buy # 총 수익 금액
total_profit_rate = (total_eval - total_buy) / total_buy * 100 if total_buy > 0 else 0

# -------------------------------
# 📊 계좌 요약 (수익 금액 추가)
# -------------------------------
def card(title, value, color="black"):
    return f"""
    <div style="padding:10px; border:1px solid #eee; border-radius:10px; background:#fafafa; text-align:center; margin:5px;">
        <div style="font-size:12px; color:gray;">{title}</div>
        <div style="font-size:18px; font-weight:bold; color:{color};">{value}</div>
    </div>
    """

st.markdown("---")
st.markdown("### 📊 계좌 요약")

# 첫 번째 줄: 예수금, 총 매수액, 총 수익(추가됨)
row1_1, row1_2, row1_3 = st.columns(3)
with row1_1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
with row1_2: st.markdown(card("📥 총 매수액", f"{int(total_buy):,}원"), unsafe_allow_html=True)
with row1_3: 
    amt_color = "#e63946" if total_profit_amt > 0 else "#457b9d" if total_profit_amt < 0 else "black"
    st.markdown(card("💵 총 수익", f"{int(total_profit_amt):+,}원", amt_color), unsafe_allow_html=True)

# 두 번째 줄: 총 평가액, 총 자산, 총 수익률
row2_1, row2_2, row2_3 = st.columns(3)
with row2_1: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
with row2_2: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
with row2_3: 
    rate_color = "#e63946" if total_profit_rate > 0 else "#457b9d" if total_profit_rate < 0 else "black"
    st.markdown(card("📊 총 수익률", f"{total_profit_rate:+.2f}%", rate_color), unsafe_allow_html=True)

# -------------------------------
# 📋 보유 종목 현황 (예수금 비중 포함)
# -------------------------------
st.markdown("### 📋 보유 종목 현황")

final_data = []
for r in result_list:
    weight = (r[4] / total_asset * 100) if total_asset > 0 else 0
    final_data.append(r + [round(weight, 1)])

cash_weight = (cash / total_asset * 100) if total_asset > 0 else 0
final_data.append(["💰 예수금 합계", None, None, None, int(cash), None, round(cash_weight, 1)])

df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])

def color_profit(val):
    if pd.isna(val) or isinstance(val, str): return ''
    color = '#e63946' if val > 0 else '#457b9d' if val < 0 else 'black'
    return f'color: {color};'

styled_df = df_final.style.format({
    "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "평가액": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-",
    "비중(%)": lambda x: f"{x:.1f}%" if pd.notnull(x) else "0.0%"
}).map(color_profit, subset=['수익률']).set_properties(**{'text-align': 'right'})

st.dataframe(styled_df, use_container_width=True)