import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json

# 데이터 로드 직후에 추가해서 확인용으로 사용
df = pd.read_excel(target_file)
st.write("불러온 데이터 미리보기:", df.head()) # 이 줄을 추가해서 데이터가 나오는지 확인
# -------------------------------
# 💾 데이터 저장 및 로드 (예수금 + 수동 현재가)
# -------------------------------
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"cash": {}, "manual_prices": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# -------------------------------
# 📱 화면 구성 및 스타일
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오 관리")
st.markdown("""
<style>
.main .block-container { max-width: 900px; padding-top: 2rem; }
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
    st.error("❗ 엑셀 파일이 존재하지 않습니다.")
    st.stop()

selected_account = st.sidebar.selectbox("계좌를 선택하세요", ["전체 계좌"] + list(existing_files.keys()))
db = load_data()

# -------------------------------
# 💰 예수금 및 현재가 로직
# -------------------------------
if selected_account == "전체 계좌":
    df = pd.concat([pd.read_excel(p) for p in existing_files.values()], ignore_index=True)
    cash = sum([db["cash"].get(acc, 1000000) for acc in existing_files.keys()])
    st.info(f"💡 전체 계좌 합산 예수금: {cash:,}원")
else:
    df = pd.read_excel(existing_files[selected_account])
    saved_cash = db["cash"].get(selected_account, 1000000)
    cash = st.number_input(f"💰 {selected_account} 예수금 설정", value=saved_cash, step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

# -------------------------------
# 🔹 시세 데이터 크롤링
# -------------------------------
code_map = {row["종목"]: str(row["코드"]).zfill(6) for _, row in df.iterrows()}

@st.cache_data(ttl=60)
def get_price(code):
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={code}"
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        # 장마감 후에도 가장 정확한 숫자를 가져오기 위해 상단 현재가 선택
        price_tag = soup.select_one(".no_today .blind")
        return int(price_tag.text.replace(",", "")) if price_tag else 0
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

# -------------------------------
# 💹 현재가 입력 (저장 기능 포함)
# -------------------------------
st.markdown("### 💹 실시간 시세 (수동 입력 시 저장됨)")
price_dict = {}
cols = st.columns(4)
for i, name in enumerate(active_stocks):
    avg_p = int(portfolio[name]["total_buy"] / portfolio[name]["qty"])
    
    # 1. 저장된 수동 가격이 있는지 확인
    # 2. 없으면 네이버에서 가져옴
    saved_price = db["manual_prices"].get(name)
    auto_p = get_price(code_map.get(name, "000000"))
    
    initial_val = saved_price if saved_price else (auto_p if auto_p > 0 else avg_p)
    
    with cols[i % 4]:
        # 'p_'를 키에 포함하여 계좌별 입력창 분리
        price_input = st.number_input(name, value=int(initial_val), key=f"inp_{name}")
        
        # 값이 변경되면 파일에 저장
        if price_input != saved_price:
            db["manual_prices"][name] = price_input
            save_data(db)
        price_dict[name] = price_input

# -------------------------------
# 📊 집계 및 요약
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
    result_list.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])

total_asset = cash + total_eval
total_profit_amt = total_eval - total_buy
total_profit_rate = (total_eval - total_buy) / total_buy * 100 if total_buy > 0 else 0

# 계좌 요약 카드 함수
def card(title, value, color="black"):
    return f"""<div style="padding:10px; border:1px solid #eee; border-radius:10px; background:#fafafa; text-align:center; margin:5px;">
    <div style="font-size:12px; color:gray;">{title}</div>
    <div style="font-size:18px; font-weight:bold; color:{color};">{value}</div></div>"""

st.markdown("---")
st.markdown("### 📊 계좌 요약")
r1_1, r1_2, r1_3 = st.columns(3)
with r1_1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
with r1_2: st.markdown(card("📥 총 매수액", f"{int(total_buy):,}원"), unsafe_allow_html=True)
with r1_3: 
    amt_c = "#e63946" if total_profit_amt > 0 else "#457b9d" if total_profit_amt < 0 else "black"
    st.markdown(card("💵 총 수익", f"{int(total_profit_amt):+,}원", amt_c), unsafe_allow_html=True)

r2_1, r2_2, r2_3 = st.columns(3)
with r2_1: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
with r2_2: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
with r2_3: 
    rate_c = "#e63946" if total_profit_rate > 0 else "#457b9d" if total_profit_rate < 0 else "black"
    st.markdown(card("📊 총 수익률", f"{total_profit_rate:+.2f}%", rate_c), unsafe_allow_html=True)

# -------------------------------
# 📋 보유 종목 현황 테이블
# -------------------------------
st.markdown("### 📋 보유 종목 현황")
final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1)] for r in result_list]
final_data.append(["💰 예수금 합계", None, None, None, int(cash), None, round(cash/total_asset*100, 1)])

df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])

def color_p(val):
    if pd.isna(val) or isinstance(val, str): return ''
    return f'color: {"#e63946" if val > 0 else "#457b9d" if val < 0 else "black"};'

st.dataframe(df_final.style.format({
    "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "평가액": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-",
    "비중(%)": lambda x: f"{x:.1f}%" if pd.notnull(x) else "0.0%"
}).map(color_p, subset=['수익률']).set_properties(**{'text-align': 'right'}), use_container_width=True)