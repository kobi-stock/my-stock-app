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
# 📱 2. 화면 구성
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오 관리", layout="centered")

# -------------------------------
# 📂 3. 구글 시트 탭별 연동 설정 (핵심 수정)
# -------------------------------
# 각 탭의 URL 주소 끝에 있는 gid 번호를 여기에 정확히 입력해야 합니다.
# 스크린샷 기준으로 설정해 두었습니다.
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"

TAB_INFO = {
    "기본 계좌": "0",       # '기본' 탭 gid
    "한국투자증권": "1360145887"  # '한투' 탭 gid (실제 시트 주소창에서 gid= 뒤의 숫자를 확인하세요)
}

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try:
        url = f"{SHEET_BASE}&gid={gid}"
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"시트 로드 실패: {e}")
        return pd.DataFrame()

# -------------------------------
# 📂 4. 사이드바 계좌 선택
# -------------------------------
st.sidebar.title("📂 계좌 관리")
selected_account = st.sidebar.selectbox("표시할 계좌를 선택하세요", ["전체 계좌"] + list(TAB_INFO.keys()))

db = load_data()

# 데이터 로드 로직
if selected_account == "전체 계좌":
    dfs = []
    for name, gid in TAB_INFO.items():
        temp_df = load_sheet_data(gid)
        if not temp_df.empty:
            dfs.append(temp_df)
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
else:
    df = load_sheet_data(TAB_INFO[selected_account])

if df.empty:
    st.warning("구글 시트 데이터를 가져올 수 없습니다. 공유 설정을 확인해 주세요.")
    st.stop()

st.title(f"📊 {selected_account} 포트폴리오")
st.info("💡 구글 시트의 해당 탭 데이터를 실시간으로 읽어옵니다.")

# -------------------------------
# 💰 5. 예수금 설정
# -------------------------------
# 전체 계좌일 때는 각 계좌 예수금 합산 표시
if selected_account == "전체 계좌":
    cash = sum([db["cash"].get(name, 1000000) for name in TAB_INFO.keys()])
    st.info(f"💡 전체 합산 예수금: {cash:,}원")
else:
    saved_cash = db["cash"].get(selected_account, 1000000)
    cash = st.number_input(f"💰 {selected_account} 예수금 설정", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

# -------------------------------
# 🔹 6. 시세 크롤링 및 계산 (기존 로직 최적화)
# -------------------------------
@st.cache_data(ttl=10)
def get_price(code):
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={str(code).zfill(6)}"
        res = requests.get(url, timeout=3)
        soup = BeautifulSoup(res.text, "html.parser")
        price_tag = soup.select_one(".no_today .blind")
        return int(price_tag.text.replace(",", "")) if price_tag else 0
    except: return 0

portfolio = {}
for _, row in df.iterrows():
    try:
        name, qty, p, action = row["종목"], row["수량"], row["가격"], row["구분"]
        code = str(row["코드"]).split('.')[0].zfill(6) # 소수점 생김 방지
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
# 💹 7. 시세 입력 및 결과 출력
# -------------------------------
price_dict = {}
if active_stocks:
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        data = portfolio[name]
        saved_p = db["manual_prices"].get(name)
        auto_p = get_price(data["code"])
        init_val = saved_p if saved_p else (auto_p if auto_p > 0 else int(data["total_buy"]/data["qty"]))
        
        with cols[i % 4]:
            p_input = st.number_input(name, value=int(init_val), key=f"inp_{name}")
            if p_input != saved_p:
                db["manual_prices"][name] = p_input
                save_data(db)
            price_dict[name] = p_input

    # 요약 정보 계산
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

    # 카드 디자인 및 테이블 출력 (생략된 기존 디자인 코드 적용됨)
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

    st.markdown("### 📋 보유 종목 현황")
    final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1) if total_asset > 0 else 0] for r in result_list]
    final_data.append(["💰 예수금 합계", None, None, None, int(cash), None, round(cash/total_asset*100, 1) if total_asset > 0 else 0])
    df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    st.dataframe(df_final, use_container_width=True)