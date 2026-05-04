import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json
import re

# -------------------------------
# 💾 1. 데이터 관리 및 초기화
# -------------------------------
DATA_FILE = "portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                for key in ["cash", "manual_prices", "api_keys"]:
                    if key not in data: data[key] = {}
                return data
        except:
            return {"cash": {}, "manual_prices": {}, "api_keys": {}}
    return {"cash": {}, "manual_prices": {}, "api_keys": {}}

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
# 📱 3. UI 및 사이드바
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
st.markdown("<style>.main .block-container { max-width: 900px; padding-top: 2rem; }</style>", unsafe_allow_html=True)

st.sidebar.title("🔐 API 설정")
ak = st.sidebar.text_input("App Key", value=st.session_state.db["api_keys"].get("key", ""), type="password")
as_ = st.sidebar.text_input("App Secret", value=st.session_state.db["api_keys"].get("secret", ""), type="password")
if st.sidebar.button("API 정보 저장"):
    st.session_state.db["api_keys"] = {"key": ak, "secret": as_}
    save_data(st.session_state.db)
    st.sidebar.success("저장 완료")

if st.sidebar.button("🔄 모든 수동 시세 초기화"): # 이 버튼을 누르면 보령의 2225가 사라집니다.[cite: 1]
    st.session_state.db["manual_prices"] = {}
    save_data(st.session_state.db)
    st.rerun()

st.sidebar.divider()
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

# 📂 4. 데이터 로드[cite: 1]
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

# 💹 5. 시세 엔진[cite: 1]
token = get_kis_token(ak, as_) if ak and as_ else None

@st.cache_data(ttl=5)
def fetch_live_price(code):
    if not code or pd.isna(code): return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    
    if token:
        p = get_kis_price(clean_code, ak, as_, token)
        if p: return p
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={clean_code}"
        h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=h, timeout=2)
        soup = BeautifulSoup(r.text, "html.parser")
        price = soup.select_one(".no_today .blind").text.replace(",", "")
        return int(price)
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

# 🏦 7. 메인 화면
st.title(f"📊 {selected_account} 현황")
price_dict = {}

if active_stocks:
    st.markdown("### 💹 실시간 시세 (틀릴 경우 직접 수정 가능)")
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        live_p = fetch_live_price(portfolio[name]["code"])
        saved_p = st.session_state.db["manual_prices"].get(name)
        
        # 저장된 수동 시세가 있으면 그걸 쓰고, 없으면 실시간 시세를 사용[cite: 1]
        display_val = saved_p if saved_p is not None else live_p
        
        with cols[i % 4]:
            p_in = st.number_input(f"{name} ({live_p:,})", value=int(display_val), key=f"inp_{name}")
            if p_in != saved_p:
                st.session_state.db["manual_prices"][name] = p_in
                save_data(st.session_state.db)
            price_dict[name] = p_in

    # 집계 로직
    total_eval, total_buy_sum, res_data = 0, 0, []
    for name in active_stocks:
        d = portfolio[name]; curr_p = price_dict[name]; avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p; total_eval += eval_amt; total_buy_sum += d["total_buy"]
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        res_data.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])

    total_asset = cash + total_eval
    total_profit = total_eval - total_buy_sum
    total_rate = (total_profit / total_buy_sum * 100) if total_buy_sum > 0 else 0

    def card(t, v, c="black"):
        return f'<div style="padding:10px; border:1px solid #eee; border-radius:10px; background:#fafafa; text-align:center; margin:5px;"><div style="font-size:12px; color:gray;">{t}</div><div style="font-size:18px; font-weight:bold; color:{c};">{v}</div></div>'

    st.divider()
    c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3)
    with c1: st.markdown(card("💰 예수금", f"{int(cash):,}원"), unsafe_allow_html=True)
    with c2: st.markdown(card("📥 총 매수액", f"{int(total_buy_sum):,}원"), unsafe_allow_html=True)
    with c3: st.markdown(card("💵 총 수익", f"{int(total_profit):+,}원", "#e63946" if total_profit > 0 else "#457b9d"), unsafe_allow_html=True)
    with c4: st.markdown(card("📈 총 평가액", f"{int(total_eval):,}원"), unsafe_allow_html=True)
    with c5: st.markdown(card("🏦 총 자산", f"{int(total_asset):,}원"), unsafe_allow_html=True)
    with c6: st.markdown(card("📊 수익률", f"{total_rate:+.2f}%", "#e63946" if total_rate > 0 else "#457b9d"), unsafe_allow_html=True)

    # 테이블 및 색상 적용[cite: 1]
    st.markdown("### 📋 보유 종목 현황")
    final_rows = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1)] for r in res_data]
    final_rows.append(["💰 예수금 합계", None, None, None, int(cash), None, round(cash/total_asset*100, 1)])
    df_final = pd.DataFrame(final_rows, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])

    def color_profit(val):
        if pd.isna(val) or isinstance(val, str): return ""
        return f"color: {'#e63946' if val > 0 else '#457b9d' if val < 0 else 'black'}; font-weight: bold;"

    st.dataframe(df_final.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
    }).map(color_profit, subset=["수익률"]), use_container_width=True)