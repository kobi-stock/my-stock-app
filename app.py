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
table {
    width: 100%;
    border-collapse: collapse;
}
th, td {
    padding: 6px;
    border-bottom: 1px solid #ddd;
}
th {
    text-align: center;
}
td.num {
    text-align: right;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 내 포트폴리오")

# -------------------------------
# 💰 예수금 (URL 저장)
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
# 💹 현재가 입력
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
rows = []
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

    rows.append({
        "종목": name,
        "수량": data["qty"],
        "평단": avg_price,
        "현재가": current_price,
        "평가액": eval_amount,
        "수익률": profit_rate
    })

total_asset = cash + total_eval
total_profit_rate = (total_eval - total_buy) / total_buy * 100 if total_buy else 0

# -------------------------------
# 📊 계좌 요약
# -------------------------------
st.markdown("### 📊 계좌 요약")

col1, col2, col3 = st.columns(3)

col1.metric("💰 예수금", f"{cash:,} 원")
col2.metric("🏦 총 자산", f"{int(total_asset):,} 원")
col3.metric("📊 총 수익률", f"{round(total_profit_rate,1)}%")

# -------------------------------
# 📋 HTML 테이블 출력 (정렬 완벽 적용)
# -------------------------------
st.markdown("### 📋 보유 종목 현황")

html = "<table>"
html += "<tr><th>종목</th><th>수량</th><th>평단</th><th>현재가</th><th>평가액</th><th>수익률</th><th>비중</th></tr>"

for r in rows:
    weight = (r["평가액"] / total_asset * 100) if total_asset else 0
    color = "red" if r["수익률"] > 0 else "blue"

    html += f"""
    <tr>
        <td>{r['종목']}</td>
        <td class='num'>{int(r['수량']):,}</td>
        <td class='num'>{int(r['평단']):,}</td>
        <td class='num'>{int(r['현재가']):,}</td>
        <td class='num'>{int(r['평가액']):,}</td>
        <td class='num' style='color:{color}'>{r['수익률']:.1f}%</td>
        <td class='num'>{weight:.1f}%</td>
    </tr>
    """

html += "</table>"

st.markdown(html, unsafe_allow_html=True)