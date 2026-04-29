import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup

# -------------------------------
# 📱 화면 폭 제한
# -------------------------------
st.markdown("""
<style>
.main .block-container {
    max-width: 900px;
    padding-top: 2rem;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 내 포트폴리오")

# -------------------------------
# 💰 예수금 (URL 저장 방식)
# -------------------------------
params = st.query_params

try:
    cash = int(params.get("cash", 1000000))
except:
    cash = 1000000

cash_input = st.number_input("💰 예수금", value=cash)
st.query_params["cash"] = str(cash_input)
cash = cash_input

# -------------------------------
# 📂 엑셀 불러오기
# -------------------------------
df = pd.read_excel("trade_log.xlsx")

# -------------------------------
# 🔹 종목코드 매핑
# -------------------------------
code_map = {}
for _, row in df.iterrows():
    code_map[row["종목"]] = str(row["코드"]).zfill(6)

# -------------------------------
# 🔹 현재가 가져오기
# -------------------------------
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
    name = row["종목"]
    qty = row["수량"]
    price = row["가격"]
    action = row["구분"]

    if name not in portfolio:
        portfolio[name] = {"qty": 0, "total_buy": 0}

    if action == "매수":
        portfolio[name]["qty"] += qty
        portfolio[name]["total_buy"] += qty * price

    elif action == "매도":
        if portfolio[name]["qty"] > 0:
            avg_price = portfolio[name]["total_buy"] / portfolio[name]["qty"]
            portfolio[name]["qty"] -= qty
            portfolio[name]["total_buy"] -= avg_price * qty

        if portfolio[name]["qty"] <= 0:
            portfolio[name]["qty"] = 0
            portfolio[name]["total_buy"] = 0

# -------------------------------
# 💹 현재가 입력 (가로 배치)
# -------------------------------
st.markdown("### 💹 현재가")

price_dict = {}
names = [n for n, d in portfolio.items() if d["qty"] > 0]

for i in range(0, len(names), 4):
    cols = st.columns(4)
    for j, name in enumerate(names[i:i+4]):
        data = portfolio[name]
        avg_price = data["total_buy"] / data["qty"]

        auto_price = get_price(code_map.get(name, "000000"))

        with cols[j]:
            price = st.number_input(
                name,
                value=int(auto_price) if auto_price > 0 else int(avg_price),
                key=f"price_{name}"
            )
            price_dict[name] = price

# -------------------------------
# 📊 계산
# -------------------------------
result = []
total_eval = 0
total_buy = sum([d["total_buy"] for d in portfolio.values()])

for name, data in portfolio.items():
    if data["qty"] == 0:
        continue

    avg_price = data["total_buy"] / data["qty"]
    current_price = price_dict[name]

    eval_amount = data["qty"] * current_price
    total_eval += eval_amount

    profit_rate = (current_price - avg_price) / avg_price * 100 if avg_price else 0

    result.append([
        name,
        data["qty"],
        int(avg_price),
        current_price,
        int(eval_amount),
        round(profit_rate, 2)
    ])

total_asset = cash + total_eval
total_profit_rate = (total_eval - total_buy) / total_buy * 100 if total_buy else 0

# -------------------------------
# 📊 비중 계산 + 예수금 포함
# -------------------------------
final_result = []

for row in result:
    eval_amount = row[4]
    weight = (eval_amount / total_asset * 100) if total_asset > 0 else 0
    final_result.append(row + [round(weight, 2)])

# 예수금 추가
cash_weight = (cash / total_asset * 100) if total_asset > 0 else 0

final_result.append([
    "💰 예수금",
    "",
    "",
    "",
    int(cash),
    "",
    round(cash_weight, 2)
])

# -------------------------------
# 📊 계좌 요약 카드
# -------------------------------
def card(title, value):
    return f"""
    <div style="
        padding:8px;
        border:1px solid #ddd;
        border-radius:8px;
        margin-bottom:5px;
        background:#fafafa">
        <div style="font-size:12px; color:gray">{title}</div>
        <div style="font-size:18px; font-weight:bold">{value}</div>
    </div>
    """

st.markdown("### 📊 계좌 요약")

c1, c2 = st.columns(2)
with c1:
    st.markdown(card("💰 예수금", f"{int(cash):,} 원"), unsafe_allow_html=True)
with c2:
    st.markdown(card("📥 총 매수액", f"{int(total_buy):,} 원"), unsafe_allow_html=True)

c3, c4, c5 = st.columns(3)
with c3:
    st.markdown(card("📈 총 평가액", f"{int(total_eval):,} 원"), unsafe_allow_html=True)
with c4:
    st.markdown(card("🏦 총 자산", f"{int(total_asset):,} 원"), unsafe_allow_html=True)
with c5:
    color = "red" if total_profit_rate > 0 else "blue"
    st.markdown(card("📊 총 수익률",
        f"<span style='color:{color}'>{round(total_profit_rate,2)}%</span>"),
        unsafe_allow_html=True)

# -------------------------------
# 📋 테이블 출력
# -------------------------------
df_result = pd.DataFrame(final_result, columns=[
    "종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"
])

st.markdown("### 📋 보유 종목 현황")
st.dataframe(df_result)