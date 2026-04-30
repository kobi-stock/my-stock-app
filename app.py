import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json

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
# 📱 2. 화면 구성 및 스타일
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오 관리", layout="wide")
st.markdown("""
<style>
.main .block-container { max-width: 1100px; padding-top: 2rem; }
div.stNumberInput > label { font-weight: bold; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# 📂 3. 구글 시트 정보 설정
# -------------------------------
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {
    "기본 계좌": "0",
    "한국투자증권": "1939408144"
}

@st.cache_data(ttl=5)
def load_sheet_data(gid):
    try:
        url = f"{SHEET_BASE}&gid={gid}"
        df = pd.read_csv(url, dtype={'코드': str})
        return df
    except Exception as e:
        st.error(f"⚠️ 시트 로드 실패: {e}")
        return pd.DataFrame()

# -------------------------------
# 📂 4. 사이드바 관리
# -------------------------------
st.sidebar.title("📂 계좌 관리")
selected_account = st.sidebar.selectbox("표시할 계좌를 선택하세요", ["전체 계좌"] + list(TAB_INFO.keys()))

db = load_data()

if st.sidebar.button("🔄 저장된 수동 가격 초기화"):
    db["manual_prices"] = {}
    save_data(db)
    st.sidebar.success("가격이 초기화되었습니다.")
    st.rerun()

# 데이터 로드 로직
if selected_account == "전체 계좌":
    dfs = []
    for gid in TAB_INFO.values():
        temp = load_sheet_data(gid)
        if not temp.empty: dfs.append(temp)
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
else:
    df = load_sheet_data(TAB_INFO[selected_account])

if df.empty:
    st.warning("데이터를 가져올 수 없습니다. 시트를 확인해 주세요.")
    st.stop()

# -------------------------------
# 🔹 5. 실시간 시세 크롤링 함수
# -------------------------------
@st.cache_data(ttl=10)
def get_live_price(code):
    if not code or str(code) == "nan": return 0
    try:
        clean_code = str(code).split('.')[0].zfill(6)
        url = f"https://finance.naver.com/item/main.nhn?code={clean_code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=2)
        soup = BeautifulSoup(res.text, "html.parser")
        price_tag = soup.select_one(".no_today .blind")
        return int(price_tag.text.replace(",", "")) if price_tag else 0
    except: return 0

# -------------------------------
# 📊 6. 포트폴리오 계산 (날짜 열 무시 로직 포함)
# -------------------------------
portfolio = {}
for _, row in df.iterrows():
    try:
        name, qty, p, action = row["종목"], row["수량"], row["가격"], row["구분"]
        code = str(row["코드"]).split('.')[0].zfill(6)
        if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * p
        elif action == "매도":
            if portfolio[name]["qty"] > 0:
                avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
                portfolio[name]["qty"] -= qty
                portfolio[name]["total_buy"] -= avg_p * qty
    except: continue

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# -------------------------------
# 💹 7. 메인 화면 및 현재가 입력
# -------------------------------
st.title(f"📊 {selected_account} 현황")
price_dict = {}

if active_stocks:
    st.markdown("### 💹 현재가 확인")
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        data = portfolio[name]
        live_p = get_live_price(data["code"])
        saved_p = db["manual_prices"].get(name)
        display_val = saved_p if saved_p else live_p
        
        with cols[i % 4]:
            p_input = st.number_input(f"{name} (실시간:{live_p:,})", value=int(display_val), key=f"p_{name}")
            if p_input != saved_p and p_input != live_p:
                db["manual_prices"][name] = p_input
                save_data(db)
            price_dict[name] = p_input

    # -------------------------------
    # 💰 8. 예수금 설정
    # -------------------------------
    if selected_account == "전체 계좌":
        cash = sum([db["cash"].get(name, 1000000) for name in TAB_INFO.keys()])
    else:
        saved_cash = db["cash"].get(selected_account, 1000000)
        cash = st.number_input(f"💰 {selected_account} 예수금 설정", value=int(saved_cash), step=10000)
        if cash != saved_cash:
            db["cash"][selected_account] = cash
            save_data(db)

    # -------------------------------
    # 📈 9. 요약 통계 계산
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
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
    with c2: st.markdown(card("📥 총 매수액", f"{int(total_buy):,}원"), unsafe_allow_html=True)
    with c3: 
        a_c = "#e63946" if total_profit_amt > 0 else "#457b9d" if total_profit_amt < 0 else "black"
        st.markdown(card("💵 총 수익", f"{int(total_profit_amt):+,}원", a_c), unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3)
    with c4: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
    with c5: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
    with c6: 
        r_c = "#e63946" if total_profit_rate > 0 else "#457b9d" if total_profit_rate < 0 else "black"
        st.markdown(card("📊 총 수익률", f"{total_profit_rate:+.2f}%", r_c), unsafe_allow_html=True)

    # -------------------------------
    # 📋 10. 보유 종목 현황 테이블 (색상 적용)
    # -------------------------------
    st.markdown("### 📋 보유 종목 현황")
    
    # 비중 계산 포함 데이터 생성
    table_rows = []
    for r in result_list:
        weight = (r[4] / total_asset * 100) if total_asset > 0 else 0
        table_rows.append([r[0], r[1], r[2], r[3], r[4], r[5], round(weight, 1)])
    
    # 예수금 행 추가
    cash_weight = (cash / total_asset * 100) if total_asset > 0 else 0
    table_rows.append(["💰 예수금 합계", None, None, None, int(cash), None, round(cash_weight, 1)])

    df_final = pd.DataFrame(table_rows, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])

    # 수익률 색상 스타일 함수
    def color_profit(val):
        if pd.isna(val) or isinstance(val, str): return ""
        if val > 0: return "color: #e63946; font-weight: bold;" # 빨간색
        if val < 0: return "color: #457b9d; font-weight: bold;" # 파란색
        return ""

    st.dataframe(df_final.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-",
        "비중(%)": lambda x: f"{x:.1f}%"
    }).map(color_profit, subset=["수익률"]), use_container_width=True)
else:
    st.info("보유 종목이 없습니다.")