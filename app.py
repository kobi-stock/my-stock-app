import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json
import time

# -------------------------------
# 💾 1. 데이터 저장 및 로드
# -------------------------------
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"cash": {}, "manual_prices": {}}
    return {"cash": {}, "manual_prices": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# -------------------------------
# 📱 2. 화면 구성
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오 관리", layout="centered")
st.markdown("""
<style>
.main .block-container { max-width: 900px; padding-top: 2rem; }
div.stNumberInput > label { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# 📂 3. 사이드바 및 파일 처리
# -------------------------------
st.sidebar.title("📂 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("수정된 엑셀 파일을 여기에 올리세요", type=["xlsx"])

st.sidebar.markdown("---")
st.sidebar.title("📂 계좌 관리")
file_options = {
    "기본 계좌": "trade_log.xlsx",
    "한국투자증권": "trade_log_한투.xlsx"
}

existing_files = {name: path for name, path in file_options.items() if os.path.exists(path)}
selected_account = st.sidebar.selectbox("표시할 계좌를 선택하세요", ["전체 계좌"] + list(file_options.keys()))

db = load_data()

# -------------------------------
# 📂 4. 스마트 데이터 로드 로직 (수정됨)
# -------------------------------
try:
    # 서버(GitHub) 기본 데이터 로드
    base_dfs = {}
    for name, path in existing_files.items():
        base_dfs[name] = pd.read_excel(path)

    # 업로드된 파일이 있을 경우 처리
    if uploaded_file is not None:
        uploaded_df = pd.read_excel(uploaded_file)
        # 업로드된 파일이 어떤 계좌인지 모르므로, 현재 선택된 계좌의 데이터를 이 파일로 대체
        if selected_account != "전체 계좌":
            base_dfs[selected_account] = uploaded_df
            st.sidebar.success(f"✅ {selected_account}에 업로드 파일 적용 중")
        else:
            # 전체 계좌일 경우, 일단 업로드된 파일 내용만 보여줌 (사용자 요청 반영)
            base_dfs["업로드"] = uploaded_df
            st.sidebar.warning("⚠️ 업로드 파일만 표시 중입니다.")

    # 최종 출력용 DF 구성
    if selected_account == "전체 계좌":
        if uploaded_file is not None:
            df = base_dfs["업로드"] # 업로드 시 전체계좌도 업로드 파일 기준
        else:
            df = pd.concat(base_dfs.values(), ignore_index=True)
    else:
        df = base_dfs.get(selected_account, pd.DataFrame())

except Exception as e:
    st.error(f"데이터 로드 오류: {e}")
    st.stop()

if df.empty:
    st.warning("데이터가 없습니다. 엑셀 파일을 확인해 주세요.")
    st.stop()

# 🔍 원본 확인용
with st.expander("📝 현재 적용 중인 엑셀 데이터 미리보기"):
    st.write(df)

st.title(f"📊 {selected_account} 포트폴리오")

# -------------------------------
# 💰 5. 예수금 설정
# -------------------------------
if selected_account == "전체 계좌":
    cash = sum([db["cash"].get(acc, 0) for acc in file_options.keys()])
    st.info(f"💡 전체 계좌 합산 예수금: {cash:,}원")
else:
    saved_cash = db["cash"].get(selected_account, 1000000)
    cash = st.number_input(f"💰 {selected_account} 예수금 설정", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

# -------------------------------
# 🔹 6. 실시간 시세 크롤링 (속도 개선)
# -------------------------------
@st.cache_data(ttl=10) # 10초마다 갱신하여 속도감 향상
def get_price(code):
    if not code or code == "000000": return 0
    try:
        # 네이버 금융 메인 시세
        url = f"https://finance.naver.com/item/main.nhn?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(res.text, "html.parser")
        price_tag = soup.select_one(".no_today .blind")
        if price_tag:
            return int(price_tag.text.replace(",", ""))
        return 0
    except:
        return 0

# -------------------------------
# 📊 7. 포트폴리오 계산
# -------------------------------
portfolio = {}
for _, row in df.iterrows():
    try:
        name, qty, price, action = row["종목"], row["수량"], row["가격"], row["구분"]
        code = str(row["코드"]).zfill(6)
        if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * price
        elif action == "매도":
            if portfolio[name]["qty"] > 0:
                avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
                portfolio[name]["qty"] -= qty
                portfolio[name]["total_buy"] -= avg_p * qty
    except: continue

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# -------------------------------
# 💹 8. 시세 및 수익 계산
# -------------------------------
price_dict = {}
if active_stocks:
    st.markdown("### 💹 실시간 시세 (10초 단위 갱신)")
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        data = portfolio[name]
        saved_price = db["manual_prices"].get(name)
        auto_p = get_price(data["code"])
        
        # 기본값 설정: 수동입력 > 자동크롤링 > 평단가
        init_val = saved_price if saved_price else (auto_p if auto_p > 0 else int(data["total_buy"]/data["qty"]))
        
        with cols[i % 4]:
            price_input = st.number_input(name, value=int(init_val), key=f"inp_{name}")
            if price_input != saved_price:
                db["manual_prices"][name] = price_input
                save_data(db)
            price_dict[name] = price_input

# -------------------------------
# 📊 9. 계좌 요약 (사용자 요청: 총수익 포함)
# -------------------------------
result_list = []
total_eval, total_buy = 0, 0
for name in active_stocks:
    d = portfolio[name]
    avg_p = d["total_buy"] / d["qty"]
    curr_p = price_dict.get(name, avg_p)
    eval_amt = d["qty"] * curr_p
    total_eval += eval_amt
    total_buy += d["total_buy"]
    profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
    result_list.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])

total_asset = cash + total_eval
total_profit_amt = total_eval - total_buy
total_profit_rate = (total_eval - total_buy) / total_buy * 100 if total_buy > 0 else 0

def card(title, value, color="black"):
    return f"""<div style="padding:10px; border:1px solid #eee; border-radius:10px; background:#fafafa; text-align:center; margin:5px;">
    <div style="font-size:12px; color:gray;">{title}</div>
    <div style="font-size:18px; font-weight:bold; color:{color};">{value}</div></div>"""

st.markdown("---")
st.markdown("### 📊 계좌 요약")
c1, c2, c3 = st.columns(3)
with c1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
with c2: st.markdown(card("📥 총 매수액", f"{int(total_buy):,}원"), unsafe_allow_html=True)
with c3: 
    amt_c = "#e63946" if total_profit_amt > 0 else "#457b9d" if total_profit_amt < 0 else "black"
    st.markdown(card("💵 총 수익", f"{int(total_profit_amt):+,}원", amt_c), unsafe_allow_html=True)

c4, c5, c6 = st.columns(3)
with c4: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
with c5: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
with c6: 
    rate_c = "#e63946" if total_profit_rate > 0 else "#457b9d" if total_profit_rate < 0 else "black"
    st.markdown(card("📊 총 수익률", f"{total_profit_rate:+.2f}%", rate_c), unsafe_allow_html=True)

# 📋 보유 종황 테이블
st.markdown("### 📋 보유 종목 현황")
final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1) if total_asset > 0 else 0] for r in result_list]
final_data.append(["💰 예수금 합계", None, None, None, int(cash), None, round(cash/total_asset*100, 1) if total_asset > 0 else 0])
df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])

def color_p(val):
    if pd.isna(val) or isinstance(val, str): return ''
    return f'color: {"#e63946" if val > 0 else "#457b9d" if val < 0 else "black"};'

st.dataframe(df_final.style.format({
    "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-", "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-", "평가액": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": lambda x: f"{x:.1f}%" if pd.notnull(x) else "0.0%"
}).map(color_p, subset=['수익률']).set_properties(**{'text-align': 'right'}), use_container_width=True)