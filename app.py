import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os

# -------------------------------
# 📱 화면 구성 설정
# -------------------------------
st.set_page_config(layout="wide", page_title="내 주식 포트폴리오")
st.markdown("""
<style>
.main .block-container {
    max-width: 1000px;
    padding-top: 2rem;
}
/* 표 숫자 우측 정렬 강제 */
.stDataFrame td { text-align: right; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# 📂 계좌(엑셀 파일) 선택 사이드바
# -------------------------------
st.sidebar.title("📂 계좌 관리")
# 폴더 내에 있는 'trade_log'로 시작하는 엑셀 파일들을 자동으로 찾거나 수동으로 지정합니다.
file_options = {
    "기본 계좌": "trade_log.xlsx",
    "한국투자증권": "trade_log_한투.xlsx"
}

# 실제 존재하는 파일만 필터링
existing_files = {name: path for name, path in file_options.items() if os.path.exists(path)}

if not existing_files:
    st.error("❗ 엑셀 파일(trade_log.xlsx 등)이 파일 경로에 없습니다.")
    st.stop()

selected_account = st.sidebar.selectbox("불러올 계좌를 선택하세요", list(existing_files.keys()))
target_file = existing_files[selected_account]

st.title(f"📊 {selected_account} 포트폴리오")

# -------------------------------
# 💰 예수금 관리 (계좌별로 별도 저장)
# -------------------------------
params = st.query_params
cash_key = f"cash_{selected_account}" # 계좌별 고유 키 생성

try:
    default_cash = int(params.get(cash_key, 1000000))
except:
    default_cash = 1000000

cash_input = st.number_input(f"💰 {selected_account} 예수금 설정", value=default_cash, step=10000)
st.query_params[cash_key] = str(cash_input)
cash = cash_input

# -------------------------------
# 📂 데이터 로드 및 크롤링
# -------------------------------
df = pd.read_excel(target_file)
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
# 💹 현재가 입력란
# -------------------------------
st.markdown("### 💹 실시간 시세 (수정 가능)")
active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]
price_dict = {}
if active_stocks:
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
        auto_p = get_price(code_map.get(name, "000000"))
        with cols[i % 4]:
            price_dict[name] = st.number_input(name, value=int(auto_p) if auto_p > 0 else int(avg_p), key=f"p_{selected_account}_{name}")
else:
    st.info("현재 보유 중인 종목이 없습니다.")

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
# 📊 계좌 요약 (2줄 레이아웃)
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
r1_1, r1_2 = st.columns(2)
with r1_1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
with r1_2: st.markdown(card("📥 총 매수액", f"{int(total_buy):,}원"), unsafe_allow_html=True)

r2_1, r2_2, r2_3 = st.columns(3)
with r2_1: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
with r2_2: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
with r2_3: 
    sum_color = "#e63946" if total_profit_rate > 0 else "#457b9d" if total_profit_rate < 0 else "black"
    st.markdown(card("📊 총 수익률", f"{total_profit_rate:.2f}%", sum_color), unsafe_allow_html=True)

# -------------------------------
# 📋 보유 종목 현황 (컬러 및 우측 정렬)
# -------------------------------
st.markdown("### 📋 보유 종목 현황")

df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])

def style_portfolio(styler):
    styler.set_properties(**{'text-align': 'right'})
    def color_profit(val):
        if val is None or isinstance(val, str): return ''
        return f'color: #e63946;' if val > 0 else f'color: #457b9d;' if val < 0 else ''
    
    styler.map(color_profit, subset=['수익률'])
    styler.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "",
        "평가액": lambda x: f"{int(x):,}" if pd.notnull(x) else "",
        "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "",
        "비중(%)": lambda x: f"{x:.1f}%" if pd.notnull(x) else ""
    })
    return styler

# 스타일이 적용된 테이블 출력
st.table(style_portfolio(df_final.style))