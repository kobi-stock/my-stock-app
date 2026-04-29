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
    max-width: 1000px;
    padding-top: 2rem;
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

cash_input = st.number_input("💰 예수금", value=cash, step=10000)
st.query_params["cash"] = str(cash_input)
cash = cash_input

# -------------------------------
# 📂 엑셀 불러오기
# -------------------------------
try:
    df = pd.read_excel("trade_log.xlsx")
except FileNotFoundError:
    st.error("trade_log.xlsx 파일을 찾을 수 없습니다.")
    st.stop()

# -------------------------------
# 🔹 종목코드 매핑
# -------------------------------
code_map = {}
for _, row in df.iterrows():
    code_map[row["종목"]] = str(row["코드"]).zfill(6)

# -------------------------------
# 🔹 현재가 가져오기
# -------------------------------
@st.cache_data(ttl=60) # 1분간 캐싱하여 속도 향상
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
st.markdown("### 💹 현재가 확인 및 수정")

price_dict = {}
active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 4열로 배치
cols = st.columns(4)
for i, name in enumerate(active_stocks):
    data = portfolio[name]
    avg_price = data["total_buy"] / data["qty"]
    auto_price = get_price(code_map.get(name, "000000"))
    
    with cols[i % 4]:
        price = st.number_input(
            name,
            value=int(auto_price) if auto_price > 0 else int(avg_price),
            key=f"price_{name}",
            step=100
        )
        price_dict[name] = price

# -------------------------------
# 📊 데이터 집계
# -------------------------------
result_data = []
total_eval = 0
total_buy = sum([d["total_buy"] for d in portfolio.values() if d["qty"] > 0])

for name in active_stocks:
    data = portfolio[name]
    avg_price = data["total_buy"] / data["qty"]
    current_price = price_dict[name]
    eval_amount = data["qty"] * current_price
    total_eval += eval_amount
    
    profit_rate = (current_price - avg_price) / avg_price * 100 if avg_price else 0

    result_data.append({
        "종목": name,
        "수량": data["qty"],
        "평단": int(avg_price),
        "현재가": current_price,
        "평가액": int(eval_amount),
        "수익률": round(profit_rate, 2)
    })

total_asset = cash + total_eval
total_profit_rate = (total_eval - total_buy) / total_buy * 100 if total_buy > 0 else 0

# 비중 계산 및 예수금 행 추가
for row in result_data:
    row["비중(%)"] = round((row["평가액"] / total_asset * 100), 2) if total_asset > 0 else 0

# -------------------------------
# 📊 계좌 요약 카드
# -------------------------------
def card(title, value):
    return f"""
    <div style="padding:10px; border:1px solid #ddd; border-radius:8px; background:#fafafa; text-align:center;">
        <div style="font-size:13px; color:gray">{title}</div>
        <div style="font-size:20px; font-weight:bold">{value}</div>
    </div>
    """

st.markdown("---")
st.markdown("### 📊 계좌 요약")

c1, c2, c3, c4, c5 = st.columns(5)
with c1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
with c2: st.markdown(card("📥 총 매수액", f"{int(total_buy):,}원"), unsafe_allow_html=True)
with c3: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
with c4: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
with c5:
    color = "#e63946" if total_profit_rate > 0 else "#457b9d"
    st.markdown(card("📊 총 수익률", f"<span style='color:{color}'>{total_profit_rate:.2f}%</span>"), unsafe_allow_html=True)

# -------------------------------
# 📋 보유 종목 현황 테이블
# -------------------------------
st.markdown("### 📋 보유 종목 현황")

df_result = pd.DataFrame(result_data)

# 예수금 행 데이터 생성
cash_row = pd.DataFrame([{
    "종목": "💰 예수금",
    "수량": None,
    "평단": None,
    "현재가": None,
    "평가액": int(cash),
    "수익률": None,
    "비중(%)": round((cash / total_asset * 100), 2) if total_asset > 0 else 0
}])

df_final = pd.concat([df_result, cash_row], ignore_index=True)

# 컬럼 설정 (우측 정렬 및 포맷팅 핵심 부분)
st.dataframe(
    df_final,
    use_container_width=True,
    hide_index=True,
    column_config={
        "종목": st.column_config.TextColumn("종목", width="medium"),
        "수량": st.column_config.NumberColumn("수량", format="%d"),
        "평단": st.column_config.NumberColumn("평단", format="%d"),
        "현재가": st.column_config.NumberColumn("현재가", format="%d"),
        "평가액": st.column_config.NumberColumn("평가액", format="%d"),
        "수익률": st.column_config.NumberColumn("수익률", format="%.2f%%"),
        "비중(%)": st.column_config.NumberColumn("비중(%)", format="%.1f%%"),
    }
)