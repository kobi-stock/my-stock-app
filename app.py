import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json
import re
import datetime

# -------------------------------
# 💾 1. 데이터 관리 및 초기화
# -------------------------------
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                keys = ["cash", "manual_prices", "api_keys", "history"]
                for key in keys:
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

# -------------------------------
# 🔑 2. 한국투자증권 API
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
# 📱 3. UI 설정 및 스타일
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오", layout="centered")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem !important; }
    .main .block-container { max-width: 900px; padding-top: 1.5rem; }
    </style>
    """, unsafe_allow_html=True)

# 사이드바 설정 - API 입력을 접을 수 있게 수정
st.sidebar.title("🛠️ 환경 설정")
with st.sidebar.expander("🔐 API 정보 입력/수정", expanded=False):
    ak = st.text_input("App Key", value=st.session_state.db["api_keys"].get("key", ""), type="password")
    as_ = st.text_input("App Secret", value=st.session_state.db["api_keys"].get("secret", ""), type="password")
    if st.button("API 정보 저장"):
        st.session_state.db["api_keys"] = {"key": ak, "secret": as_}
        save_data(st.session_state.db)
        st.success("저장되었습니다!")

if st.sidebar.button("🔄 데이터 초기화 (기록 포함)"):
    st.session_state.db = {"cash": {}, "manual_prices": {}, "api_keys": {}, "history": {}}
    save_data(st.session_state.db)
    st.rerun()

st.sidebar.divider()
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

# 📂 4. 데이터 로드
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
    except: return pd.DataFrame()

if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
    cash = sum([int(st.session_state.db["cash"].get(acc, 0)) for acc in TAB_INFO.keys()])
else:
    df = load_sheet_data(TAB_INFO[selected_account])
    saved_cash = int(st.session_state.db["cash"].get(selected_account, 0))
    cash = st.number_input(f"💰 {selected_account} 예수금 설정", value=saved_cash, step=10000)
    if cash != saved_cash:
        st.session_state.db["cash"][selected_account] = cash
        save_data(st.session_state.db)

if df.empty: st.warning("데이터 로딩 중..."); st.stop()

# 💹 5. 시세 엔진 (보강됨)
token = get_kis_token(ak, as_) if ak and as_ else None

@st.cache_data(ttl=2) # 캐시 시간을 2초로 줄여 더 자주 갱신되게 함
def fetch_live_price(code):
    if not code or pd.isna(code): return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    
    # 1순위: 한국투자증권 API (가장 정확함)
    if token:
        p = get_kis_price(clean_code, ak, as_, token)
        if p and p > 0: return p
    
    # 2순위: 네이버 금융 실시간 페이지 (API 실패 시 대안)
    try:
        # 실시간성이 더 높은 다른 경로 시도
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        r = requests.get(url, timeout=2)
        data = r.json()
        return int(data['result']['areas'][0]['datas'][0]['nv'])
    except:
        try:
            url = f"https://finance.naver.com/item/main.nhn?code={clean_code}"
            h = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=h, timeout=2)
            soup = BeautifulSoup(r.text, "html.parser")
            return int(soup.select_one(".no_today .blind").text.replace(",", ""))
        except: return 0
# 📊 6. 포트폴리오 계산
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

# 🏦 7. 메인 화면 출력
st.title(f"📊 {selected_account} 현황")
price_dict = {}

if active_stocks:
    st.markdown("#### 💹 실시간 시세 수정")
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        live_p = fetch_live_price(portfolio[name]["code"])
        saved_p = st.session_state.db["manual_prices"].get(name)
        display_val = saved_p if saved_p is not None else live_p
        with cols[i % 4]:
            p_in = st.number_input(f"{name}", value=int(display_val), key=f"inp_{name}")
            if p_in != (saved_p if saved_p is not None else live_p):
                st.session_state.db["manual_prices"][name] = p_in
                save_data(st.session_state.db)
            price_dict[name] = p_in

    total_eval, total_buy_sum = 0, 0
    for name in active_stocks:
        total_eval += portfolio[name]["qty"] * price_dict[name]
        total_buy_sum += portfolio[name]["total_buy"]

    total_asset = cash + total_eval
    
    # 히스토리 기록
    today_str = datetime.date.today().isoformat()
    if st.session_state.db.get("history") is None: st.session_state.db["history"] = {}
    if st.session_state.db["history"].get(today_str) != total_asset:
        st.session_state.db["history"][today_str] = total_asset
        save_data(st.session_state.db)

    def get_history_change(days):
        hist = st.session_state.db.get("history", {})
        target_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        past_dates = sorted([d for d in hist.keys() if d <= target_date], reverse=True)
        if not past_dates: return 0.0, 0
        past_val = hist[past_dates[0]]
        return (total_asset - past_val) / past_val * 100, total_asset - past_val

    # 기간별 자산 변동
    st.divider()
    st.markdown("#### 📈 기간별 자산 변동")
    m1, m2, m3 = st.columns(3)
    d_rate, d_val = get_history_change(1); w_rate, w_val = get_history_change(7); m_rate, m_val = get_history_change(30)
    m1.metric("전일 대비", f"{int(d_val):+,}원", f"{d_rate:+.2f}%")
    m2.metric("전주 대비", f"{int(w_val):+,}원", f"{w_rate:+.2f}%")
    m3.metric("전월 대비", f"{int(m_val):+,}원", f"{m_rate:+.2f}%")

    # 계좌 요약 카드
    st.divider()
    total_profit = total_eval - total_buy_sum
    total_rate = (total_profit / total_buy_sum * 100) if total_buy_sum > 0 else 0

    c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3)
    c1.metric("💰 예수금", f"{int(cash):,}원")
    c2.metric("📥 총 매수액", f"{int(total_buy_sum):,}원")
    c3.metric("💵 총 수익", f"{int(total_profit):+,}원", f"{total_rate:+.2f}%")
    c4.metric("📈 총 평가액", f"{int(total_eval):,}원")
    c5.metric("🏦 총 자산", f"{int(total_asset):,}원")
    c6.metric("📊 수익률", f"{total_rate:+.2f}%")

    # 📋 8. 보유 종목 현황 (비중 추가 및 수익률 색상 적용)
    st.divider()
    st.markdown("#### 📋 보유 종목 현황")
    res_data = []
    
    # 1. 종목 데이터 추가
    for name in active_stocks:
        d = portfolio[name]
        curr_p = price_dict[name]
        avg_p = d["total_buy"] / d["qty"]
        profit_rate = round((curr_p - avg_p) / avg_p * 100, 2)
        eval_amount = int(d["qty"] * curr_p)
        weight = round((eval_amount / total_asset * 100), 2)
        res_data.append([name, d["qty"], int(avg_p), curr_p, eval_amount, profit_rate, weight])
    
    # 2. 예수금 데이터 추가 (비중 포함)
    cash_weight = round((cash / total_asset * 100), 2)
    res_data.append(["💰 예수금", "-", "-", "-", int(cash), "-", cash_weight])
    
    df_final = pd.DataFrame(res_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])

    # 스타일 적용 함수
    def color_profit(val):
        if val == "-": return ""
        try:
            v = float(val)
            color = '#e63946' if v > 0 else '#457b9d' if v < 0 else 'black'
            return f'color: {color}; font-weight: bold;'
        except: return ""

    st.dataframe(
        df_final.style.format({
            "수량": "{:}", "평단": "{:}", "현재가": "{:}", "평가액": "{:,.0f}", "수익률": "{:}", "비중(%)": "{:.2f}%"
        }).map(color_profit, subset=["수익률"]), 
        use_container_width=True,
        hide_index=True
    )