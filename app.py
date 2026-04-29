import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup

# -------------------------------
# 📱 화면 구성 설정
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
# 💰 예수금 관리
# -------------------------------
params = st.query_params
try:
    cash = int(params.get("cash", 1000000))
except:
    cash = 1000000

cash_input = st.number_input("💰 예수금 설정", value=cash, step=10000)
st.query_params["cash"] = str(cash_input)
cash = cash_input

# -------------------------------
# 📂 데이터 로드 및 크롤링
# -------------------------------
try:
    df = pd.read_excel("trade_log.xlsx")
except FileNotFoundError:
    st.error("trade_log.xlsx 파일을 찾을 수 없습니다.")
    st.stop()

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
# 📊 포트폴리오 계산 logic
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
# 💹 현재가 입력란 (가로 배치)
# -------------------------------
st.markdown("### 💹 실시간 시세 (수정 가능)")
active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]
price_dict = {}
cols = st.columns(4)
for i, name in enumerate(active_stocks):
    avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
    auto_p = get_price(code_map.get(name, "000000"))
    with cols[i % 4]:
        price_dict[name] = st.number_input(name, value=int(auto_p) if auto_p > 0 else int(avg_p), key=f"p_{name}")

# -------------------------------
# 📊 데이터 집계
# -------------------------------
result_list = []
total_eval, total_buy = 0, 0

for name in active_stocks:
    d = portfolio[name]
    avg_p = d["total_buy"] / d["qty"]
    curr_p = price_dict[name]
    eval_amt = d["qty"] * curr_p
    
    total_buy += d["total_buy"]
    total_eval += eval_amt
    profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
    
    result_list.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])

total_asset = cash + total_eval
total_profit_rate = (total_eval - total_buy) / total_buy * 100 if total_buy > 0 else 0

# 비중 추가 및 예수금 행 결합
final_data = []
for r in result_list:
    weight = (r[4] / total_asset * 100) if total_asset > 0 else 0
    final_data.append(r + [round(weight, 1)])

cash_weight = (cash / total_asset * 100) if total_asset > 0 else 0
final_data.append(["💰 예수금", None, None, None, int(cash), None, round(cash_weight, 1)])

# -------------------------------
# 📊 계좌 요약 (요청하신 2줄 레이아웃)
# -------------------------------
def card(title, value, color="black"):
    return f"""
    <div style="padding:10px; border:1px solid #eee; border-radius:10px; background:#fcfcfc; text-align:center; margin:5px;">
        <div style="font-size:12px; color:gray;">{title}</div>
        <div style="font-size:18px; font-weight:bold; color:{color};">{value}</div>
    </div>
    """

st.markdown("---")
st.markdown("### 📊 계좌 요약")

# 첫 번째 줄: 예수금, 총매수액
row1_1, row1_2 = st.columns(2)
with row1_1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
with row1_2: st.markdown(card("📥 총 매수액", f"{int(total_buy):,}원"), unsafe_allow_html=True)

# 두 번째 줄: 총 평가액, 총 자산, 총 수익률
row2_1, row2_2, row2_3 = st.columns(3)
with row2_1: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
with row2_2: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
with row2_3: 
    sum_color = "#e63946" if total_profit_rate > 0 else "#457b9d" if total_profit_rate < 0 else "black"
    st.markdown(card("📊 총 수익률", f"{total_profit_rate:.2f}%", sum_color), unsafe_allow_html=True)

# -------------------------------
# 📋 보유 종목 현황 (컬러 및 우측 정렬 적용)
# -------------------------------
st.markdown("### 📋 보유 종목 현황")

df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])

# 스타일 정의 함수
def style_portfolio(styler):
    # 기본 우측 정렬
    styler.set_properties(**{'text-align': 'right'})
    # 수익률 색상 지정
    def color_profit(val):
        if val is None or isinstance(val, str): return ''
        color = '#e63946' if val > 0 else '#457b9d' if val < 0 else 'black'
        return f'color: {color};'
    
    styler.map(color_profit, subset=['수익률'])
    # 천 단위 콤마 및 소수점 포맷팅
    styler.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "",
        "평가액": lambda x: f"{int(x):,}" if pd.notnull(x) else "",
        "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "",
        "비중(%)": lambda x: f"{x:.1f}%" if pd.notnull(x) else ""
    })
    return styler

st.table(style_portfolio(df_final.style)) # 정렬 유지를 위해 st.table 또는 st.dataframe(style) 사용