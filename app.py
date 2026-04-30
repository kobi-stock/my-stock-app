import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json
import time

# -------------------------------
# 💾 1. 데이터 저장/로드
# -------------------------------
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"cash": {}, "manual_prices": {}, "api_keys": {}}
    return {"cash": {}, "manual_prices": {}, "api_keys": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# -------------------------------
# 🔑 2. 한국투자증권 API 토큰 발급
# -------------------------------
def get_kis_token(app_key, app_secret):
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    try:
        res = requests.post(url, json=payload, timeout=3)
        return res.json().get("access_token")
    except:
        return None

def get_kis_price(code, app_key, token):
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": db["api_keys"].get("secret"),
        "tr_id": "FHKST01010100"
    }
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=2)
        return int(res.json()['output']['stck_prpr'])
    except:
        return None

# -------------------------------
# 📱 3. 화면 설정 및 데이터 로드
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
db = load_data()

# 사이드바 API 설정
st.sidebar.title("🔐 API 설정")
with st.sidebar.expander("한국투자증권 키 입력"):
    app_key = st.text_input("App Key", value=db.get("api_keys", {}).get("key", ""), type="password")
    app_secret = st.text_input("App Secret", value=db.get("api_keys", {}).get("secret", ""), type="password")
    if st.button("키 저장"):
        db["api_keys"] = {"key": app_key, "secret": app_secret}
        save_data(db)
        st.success("저장되었습니다!")

# 구글 시트 로드
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}

selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try:
        return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
    except: return pd.DataFrame()

if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
else:
    df = load_sheet_data(TAB_INFO[selected_account])

# -------------------------------
# 💰 4. 예수금 및 시세 엔진 선택
# -------------------------------
# 예수금 합산 로직
if selected_account == "전체 계좌":
    cash = sum([int(db["cash"].get(acc, 0)) for acc in TAB_INFO.keys()])
    st.info(f"💡 전체 계좌 예수금 합계: {cash:,}원")
else:
    saved_cash = db["cash"].get(selected_account, 0)
    cash = st.number_input(f"💰 {selected_account} 예수금", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

# API 토큰 준비
token = None
if app_key and app_secret:
    token = get_kis_token(app_key, app_secret)

# 시세 함수 (API 우선, 실패 시 크롤링)
def get_price(code):
    clean_code = str(code).split('.')[0].zfill(6)
    # 1. 한투 API 시도
    if token:
        price = get_kis_price(clean_code, app_key, token)
        if price: return price
    
    # 2. 크롤링 시도 (API 실패 시)
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={clean_code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=1.5)
        soup = BeautifulSoup(res.text, "html.parser")
        return int(soup.select_one(".no_today .blind").text.replace(",", ""))
    except: return 0

# -------------------------------
# 📊 5. 포트폴리오 계산 및 출력
# -------------------------------
portfolio = {}
for _, row in df.iterrows():
    name = str(row.iloc[1]).strip()
    if not name or name == "nan": continue
    qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
    price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
    action = str(row.iloc[4]).strip()
    code = str(row.iloc[5]).split('.')[0].zfill(6)
    
    if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
    if action == "매수":
        portfolio[name]["qty"] += qty
        portfolio[name]["total_buy"] += qty * price
    elif action == "매도" and portfolio[name]["qty"] > 0:
        avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
        portfolio[name]["qty"] -= qty
        portfolio[name]["total_buy"] -= avg_p * qty

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

if active_stocks:
    st.subheader("💹 실시간 종목 현황")
    result_list = []
    total_eval, total_buy_sum = 0, 0
    
    # 시세 일괄 호출
    for name in active_stocks:
        d = portfolio[name]
        curr_p = get_price(d["code"])
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        total_eval += eval_amt
        total_buy_sum += d["total_buy"]
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        result_list.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])
    
    # 요약 카드 및 테이블 (기존 로직 동일)
    total_asset = cash + total_eval
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("총 자산", f"{int(total_asset):,}원")
    col2.metric("총 수익", f"{int(total_eval - total_buy_sum):+,}원")
    col3.metric("수익률", f"{(total_eval - total_buy_sum)/total_buy_sum*100:+.2f}%" if total_buy_sum > 0 else "0%")

    # 테이블 출력
    final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1)] for r in result_list]
    final_data.append(["💰 예수금", None, None, None, int(cash), None, round(cash/total_asset*100, 1)])
    
    df_res = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    st.dataframe(df_res.style.format({
        "수량": "{:,.0f}", "평단": "{:,.0f}", "현재가": "{:,.0f}", "평가액": "{:,.0f}", "수익률": "{:+.2f}%", "비중(%)": "{:.1f}%"
    }), use_container_width=True)
else:
    st.info("보유 종목이 없습니다.")