import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os

# -------------------------------
# 📱 화면 구성 설정
# -------------------------------
st.markdown("""
<style>
.main .block-container {
    max-width: 1000px;
    padding-top: 2rem;
}
.stDataFrame td { text-align: right; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# 📂 계좌 선택
# -------------------------------
st.sidebar.title("📂 계좌 관리")

file_options = {
    "기본 계좌": "trade_log.xlsx",
    "한국투자증권": "trade_log_한투.xlsx"
}

existing_files = {name: path for name, path in file_options.items() if os.path.exists(path)}

if not existing_files:
    st.error("❗ 엑셀 파일이 없습니다.")
    st.stop()

selected_account = st.sidebar.selectbox(
    "불러올 계좌를 선택하세요",
    ["전체 계좌"] + list(existing_files.keys())
)

# -------------------------------
# 📂 데이터 로드
# -------------------------------
if selected_account == "전체 계좌":
    df_list = [pd.read_excel(path) for path in existing_files.values()]
    df = pd.concat(df_list, ignore_index=True)
else:
    df = pd.read_excel(existing_files[selected_account])

st.title(f"📊 {selected_account} 포트폴리오")

# -------------------------------
# 💰 예수금 처리
# -------------------------------
params = st.query_params

if selected_account == "전체 계좌":
    total_cash = 0
    for acc in existing_files.keys():
        key = f"cash_{acc}"
        try:
            total_cash += int(params.get(key, 1000000))
        except:
            total_cash += 1000000
    cash = total_cash

else:
    cash_key = f"cash_{selected_account}"
    try:
        default_cash = int(params.get(cash_key, 1000000))
    except:
        default_cash = 1000000

    cash_input = st.number_input(f"💰 {selected_account} 예수금", value=default_cash, step=10000)
    st.query_params[cash_key] = str(cash_input)
    cash = cash_input

# -------------------------------
# 🔹 종목코드 매핑
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

    if name not in portfolio:
        portfolio[name] = {"qty": 0, "total_buy": 0}

    if action == "매수":
        portfolio[name]["qty"] += qty
        portfolio[name]["total_buy"] += qty * price

    elif action == "매도":
        if portfolio[name]["qty"] > 0:
            avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
            portfolio[name]["qty"] -= qty
            portfolio[name]["total_buy"] -= avg_p * qty

        if portfolio[name]["qty"] <= 0:
            portfolio[name]["qty"] = 0
            portfolio[name]["total_buy"] = 0

# -------------------------------
# 💹 현재가 입력
# -------------------------------
st.markdown("### 💹 실시간 시세")

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]
price_dict = {}

cols = st.columns(4)
for i, name in enumerate(active_stocks):
    avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
    auto_p = get_price(code_map.get(name, "000000"))

    with cols[i % 4]:
        price_dict[name] = st.number_input(
            name,
            value=int(auto_p) if auto_p > 0 else int(avg_p),
            key=f"{selected_account}_{name}"
        )

# -------------------------------
# 📊 계산
# -------------------------------
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

    result_list.append([
        name,
        d["qty"],
        int(avg_p),
        curr_p,
        int(eval_amt),
        round(profit_r, 2)
    ])

total_asset = cash + total_eval
total_profit_rate = (total_eval - total_buy) / total_buy * 100 if total_buy else 0

# -------------------------------
# 📊 비중
# -------------------------------
final_data = []

for r in result_list:
    weight = (r[4] / total_asset * 100) if total_asset > 0 else 0
    final_data.append(r + [round(weight, 1)])

# -------------------------------
# 📊 계좌 요약
# -------------------------------
st.markdown("### 📊 계좌 요약")

col1, col2, col3 = st.columns(3)
col1.metric("💰 예수금", f"{int(cash):,}원")
col2.metric("🏦 총 자산", f"{int(total_asset):,}원")
col3.metric("📊 수익률", f"{round(total_profit_rate,1)}%")

# -------------------------------
# 📋 테이블
# -------------------------------
df_final = pd.DataFrame(final_data, columns=[
    "종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"
])

def style_table(df):
    return df.style.format({
        "수량": "{:,.0f}",
        "평단": "{:,.0f}",
        "현재가": "{:,.0f}",
        "평가액": "{:,.0f}",
        "수익률": "{:.1f}%",
        "비중(%)": "{:.1f}%"
    }).set_properties(**{"text-align": "right"})

st.markdown("### 📋 보유 종목 현황")
st.dataframe(style_table(df_final))