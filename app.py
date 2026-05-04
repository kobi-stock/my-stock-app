import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json

# -------------------------------
# 💾 1. 데이터 저장/로드 함수
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

db = load_data()

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
# 📱 3. 화면 설정 및 스타일[cite: 2]
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
st.markdown("""
<style>
.main .block-container { max-width: 900px; padding-top: 2rem; }
div.stNumberInput > label { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# 🔐 4. 사이드바 API 설정
st.sidebar.title("🔐 증권사 API 설정")
with st.sidebar.expander("한국투자증권 KIS 정보"):
    app_key = st.text_input("App Key", value=db.get("api_keys", {}).get("key", ""), type="password")
    app_secret = st.text_input("App Secret", value=db.get("api_keys", {}).get("secret", ""), type="password")
    if st.sidebar.button("API 키 저장"):
        db["api_keys"] = {"key": app_key, "secret": app_secret}
        save_data(db)
        st.sidebar.success("저장 완료!")

st.sidebar.divider()
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}
selected_account = st.sidebar.selectbox("계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

# 📂 5. 시트 데이터 로드 및 예수금 합산[cite: 2]
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
    cash = st.number_input(f"💰 {selected_account} 예수금", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

if df.empty: st.warning("데이터가 없습니다."); st.stop()

# 💹 6. 시세 엔진 (한투 API 우선)[cite: 2]
token = get_kis_token(app_key, app_secret) if app_key and app_secret else None

@st.cache_data(ttl=10)
def get_live_price(code):
    clean_code = str(code).split('.')[0].zfill(6)
    if token:
        p = get_kis_price(clean_code, app_key, app_secret, token)
        if p: return p
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={clean_code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=1.5)
        return int(BeautifulSoup(res.text, "html.parser").select_one(".no_today .blind").text.replace(",", ""))
    except: return 0

# 📊 7. 포트폴리오 계산[cite: 2]
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

# 🏦 8. 결과 카드 함수 정의[cite: 2]
def card(title, value, color="black"):
    return f"""<div style="padding:10px; border:1px solid #eee; border-radius:10px; background:#fafafa; text-align:center; margin:5px;">
    <div style="font-size:12px; color:gray;">{title}</div>
    <div style="font-size:18px; font-weight:bold; color:{color};">{value}</div></div>"""

st.title(f"📊 {selected_account} 포트폴리오")

# 📊 9. 현재가 입력 및 요약 집계[cite: 2]
price_dict = {}
if active_stocks:
    st.markdown("### 💹 실시간 시세 (수동 입력 시 저장)")
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        live_p = get_live_price(portfolio[name]["code"])
        saved_p = db["manual_prices"].get(name)
        initial_val = saved_p if saved_p else (live_p if live_p > 0 else int(portfolio[name]["total_buy"]/portfolio[name]["qty"]))
        
        with cols[i % 4]:
            current_input = st.number_input(f"{name} ({live_p:,})", value=int(initial_val), key=f"p_{name}")
            if current_input != saved_p:
                db["manual_prices"][name] = current_input
                save_data(db)
            price_dict[name] = current_input

    # 데이터 집계
    total_eval, total_buy_sum, result_list = 0, 0, []
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
    total_profit_amt = total_eval - total_buy_sum
    total_profit_rate = (total_profit_amt / total_buy_sum * 100) if total_buy_sum > 0 else 0

    # 📊 계좌 요약 (기존 디자인 복구)[cite: 2]
    st.markdown("---")
    st.markdown("### 📊 계좌 요약")
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

    # 📋 보유 종목 현황 테이블[cite: 2]
    st.markdown("### 📋 보유 종목 현황")
    final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1)] for r in result_list]
    final_data.append(["💰 예수금 합계", None, None, None, int(cash), None, round(cash/total_asset*100, 1)])
    
    df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    def color_p(val):
        if pd.isna(val) or isinstance(val, str): return ''
        return f'color: {"#e63946" if val > 0 else "#457b9d" if val < 0 else "black"}; font-weight: bold;'

    st.dataframe(df_final.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
    }).map(color_p, subset=['수익률']), use_container_width=True)
else:
    st.info("보유 종목이 없습니다.")