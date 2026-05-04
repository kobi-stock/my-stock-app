import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json
import datetime
import re

# -------------------------------
# 💾 1. 데이터 저장/로드 함수 (history 필드 추가)
# -------------------------------
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                # 누락된 필드 초기화
                for key in ["cash", "manual_prices", "api_keys", "history"]:
                    if key not in data: data[key] = {}
                return data
        except:
            return {"cash": {}, "manual_prices": {}, "api_keys": {}, "history": {}}
    return {"cash": {}, "manual_prices": {}, "api_keys": {}, "history": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'db' not in st.session_state:
    st.session_state.db = load_data()

db = st.session_state.db

# -------------------------------
# 🔑 2. 한국투자증권 API 함수
# -------------------------------
def get_kis_token(app_key, app_secret):
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret}
    try:
        res = requests.post(url, json=payload, timeout=3)
        return res.json().get("access_token")
    except: return None

def get_kis_price(code, app_key, app_secret, token):
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {"Content-Type": "application/json", "authorization": f"Bearer {token}", "appkey": app_key, "appsecret": app_secret, "tr_id": "FHKST01010100"}
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=2)
        return int(res.json()['output']['stck_prpr'])
    except: return None

# -------------------------------
# 📱 3. 화면 설정 및 스타일
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
st.markdown("""
<style>
.main .block-container { max-width: 900px; padding-top: 1.5rem; }
div.stNumberInput > label { font-weight: bold; }
[data-testid="stMetricValue"] { font-size: 1.6rem !important; }
</style>
""", unsafe_allow_html=True)

# 🔐 4. 사이드바 API 설정
st.sidebar.title("🔐 증권사 API 설정")
with st.sidebar.expander("한국투자증권 KIS 정보"):
    ak = st.text_input("App Key", value=db["api_keys"].get("key", ""), type="password")
    as_ = st.text_input("App Secret", value=db["api_keys"].get("secret", ""), type="password")
    if st.sidebar.button("API 키 저장"):
        db["api_keys"] = {"key": ak, "secret": as_}
        save_data(db)
        st.sidebar.success("저장 완료!")

st.sidebar.divider()
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

# 📂 5. 시트 데이터 로드 및 예수금
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
    except: return pd.DataFrame()

if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
    cash = sum([int(db["cash"].get(acc, 0)) for acc in TAB_INFO.keys()])
else:
    df = load_sheet_data(TAB_INFO[selected_account])
    saved_cash = db["cash"].get(selected_account, 0)
    cash = st.sidebar.number_input(f"💰 {selected_account} 예수금", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

if df.empty: st.warning("데이터가 없습니다."); st.stop()

# 💹 6. 실시간 시세 엔진 개선 (네이버 금융 API 활용)
token = get_kis_token(ak, as_) if ak and as_ else None

@st.cache_data(ttl=5)
def get_live_price_improved(code):
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    # 1. KIS API 시도
    if token:
        p = get_kis_price(clean_code, ak, as_, token)
        if p and p > 0: return p
    # 2. 네이버 실시간 폴링 API (가장 정확하고 빠름)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except: return 0

# 📊 7. 포트폴리오 계산
portfolio = {}
for _, row in df.iterrows():
    name = str(row.iloc[1]).strip()
    if not name or name == "nan": continue
    qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
    price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
    action = str(row.iloc[4]).strip()
    code = str(row.iloc[5])
    if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
    if action == "매수":
        portfolio[name]["qty"] += qty
        portfolio[name]["total_buy"] += qty * price
    elif action == "매도" and portfolio[name]["qty"] > 0:
        avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
        portfolio[name]["qty"] -= qty
        portfolio[name]["total_buy"] -= avg_p * qty

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 🏦 8. 결과 표시용 카드 함수
def card(title, value, color="black"):
    return f"""<div style="padding:10px; border:1px solid #eee; border-radius:10px; background:#fafafa; text-align:center; margin:5px;">
    <div style="font-size:12px; color:gray;">{title}</div>
    <div style="font-size:18px; font-weight:bold; color:{color};">{value}</div></div>"""

st.title(f"📊 {selected_account} 현황")

# 📉 9. 자산 변동 현황 (일별/주별/월별) 추가
price_dict = {}
if active_stocks:
    with st.expander("💹 시세 수동 수정 (필요 시)"):
        cols = st.columns(4)
        for i, name in enumerate(active_stocks):
            live_p = get_live_price_improved(portfolio[name]["code"])
            saved_p = db["manual_prices"].get(name)
            initial_val = saved_p if saved_p else (live_p if live_p > 0 else int(portfolio[name]["total_buy"]/portfolio[name]["qty"]))
            with cols[i % 4]:
                current_input = st.number_input(f"{name}", value=int(initial_val), key=f"p_{name}")
                if current_input != saved_p:
                    db["manual_prices"][name] = current_input
                    save_data(db)
                price_dict[name] = current_input

    total_eval, total_buy_sum = 0, 0
    result_list = []
    for name in active_stocks:
        d = portfolio[name]
        curr_p = price_dict[name]
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        total_eval += eval_amt
        total_buy_sum += d["total_buy"]
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        result_list.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])

    total_asset = cash + total_eval
    
    # 역사적 데이터 기록 (오늘 날짜 기준)
    today = datetime.date.today().isoformat()
    db["history"][today] = total_asset
    save_data(db)

    # 변동량 계산 함수
    def get_change(days):
        target_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        past_dates = sorted([d for d in db["history"].keys() if d <= target_date], reverse=True)
        if not past_dates: return 0.0, 0
        past_val = db["history"][past_dates[0]]
        return (total_asset - past_val) / past_val * 100, total_asset - past_val

    st.markdown("### 📈 기간별 자산 변동")
    m1, m2, m3 = st.columns(3)
    d_rate, d_val = get_change(1); w_rate, w_val = get_change(7); m_rate, m_val = get_change(30)
    m1.metric("전일 대비", f"{int(d_val):+,}원", f"{d_rate:+.2f}%")
    m2.metric("전주 대비", f"{int(w_val):+,}원", f"{w_rate:+.2f}%")
    m3.metric("전월 대비", f"{int(m_val):+,}원", f"{m_rate:+.2f}%")

    # 계좌 요약
    st.divider()
    total_profit_amt = total_eval - total_buy_sum
    total_profit_rate = (total_profit_amt / total_buy_sum * 100) if total_buy_sum > 0 else 0

    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
    with c2: st.markdown(card("📥 총 매수액", f"{int(total_buy_sum):,}원"), unsafe_allow_html=True)
    with c3: 
        a_c = "#e63946" if total_profit_amt > 0 else "#457b9d" if total_profit_amt < 0 else "black"
        st.markdown(card("💵 총 수익", f"{int(total_profit_amt):+,}원", a_c), unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3)
    with c4: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
    with c5: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
    with c6: 
        r_c = "#e63946" if total_profit_rate > 0 else "#457b9d" if total_profit_rate < 0 else "black"
        st.markdown(card("📊 총 수익률", f"{total_profit_rate:+.2f}%", r_c), unsafe_allow_html=True)

    # 테이블 출력
    st.markdown("### 📋 보유 종목 현황")
    final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1)] for r in result_list]
    df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    st.dataframe(df_final.style.format({
        "수량": "{:,.0f}", "평단": "{:,.0f}", "현재가": "{:,.0f}", 
        "평가액": "{:,.0f}", "수익률": "{:+.2f}%", "비중(%)": "{:.1f}%"
    }), use_container_width=True, hide_index=True)