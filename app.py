import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json
import time

# -------------------------------
# 💾 1. 데이터 저장 및 로드 (예수금, 수동가격, API키)
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
# 🔑 2. 한국투자증권 API 통신 함수
# -------------------------------
def get_kis_token(app_key, app_secret):
    """접근 토큰 발급"""
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

def get_kis_price(code, app_key, app_secret, token):
    """실시간 체결가 조회"""
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST01010100"
    }
    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": code
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=2)
        return int(res.json()['output']['stck_prpr'])
    except:
        return None

# -------------------------------
# 📱 3. Streamlit 앱 설정 및 사이드바
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오 관리", layout="centered")
st.markdown("""
<style>
.main .block-container { max-width: 900px; padding-top: 2rem; }
[data-testid="stMetricValue"] { font-size: 24px; }
</style>
""", unsafe_allow_html=True)

db = load_data()

# 사이드바: API 키 설정
st.sidebar.title("🔐 증권사 API 설정")
with st.sidebar.expander("한국투자증권 KIS 정보"):
    stored_key = db.get("api_keys", {}).get("key", "")
    stored_secret = db.get("api_keys", {}).get("secret", "")
    
    input_key = st.text_input("App Key", value=stored_key, type="password")
    input_secret = st.text_input("App Secret", value=stored_secret, type="password")
    
    if st.sidebar.button("API 키 저장"):
        db["api_keys"] = {"key": input_key, "secret": input_secret}
        save_data(db)
        st.sidebar.success("키가 저장되었습니다!")

# 사이드바: 계좌 선택 및 초기화
st.sidebar.divider()
st.sidebar.title("📂 데이터 관리")
TAB_INFO = {
    "기본 계좌": "0",
    "한국투자증권": "1939408144"
}
selected_account = st.sidebar.selectbox("조회할 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

if st.sidebar.button("🔄 저장된 수동 가격 초기화"):
    db["manual_prices"] = {}
    save_data(db)
    st.rerun()

# -------------------------------
# 📂 4. 구글 시트 데이터 로드
# -------------------------------
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try:
        return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
    except:
        return pd.DataFrame()

if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
else:
    df = load_sheet_data(TAB_INFO[selected_account])

if df.empty:
    st.warning("구글 시트에서 데이터를 가져올 수 없습니다. 공유 설정을 확인하세요.")
    st.stop()

# -------------------------------
# 💰 5. 예수금 관리 (전체 계좌 합산 로직)
# -------------------------------
if selected_account == "전체 계좌":
    # 각 개별 계좌의 저장된 값을 모두 더함
    total_cash = sum([int(db["cash"].get(acc, 0)) for acc in TAB_INFO.keys()])
    cash = total_cash
    st.info(f"💡 전체 계좌 예수금 합계: **{cash:,}원** (개별 계좌 화면에서 수정 가능)")
else:
    saved_cash = db["cash"].get(selected_account, 0)
    cash = st.number_input(f"💰 {selected_account} 예수금 설정", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

# -------------------------------
# 💹 6. 하이브리드 시세 엔진 (API + 크롤링)
# -------------------------------
token = None
if input_key and input_secret:
    token = get_kis_token(input_key, input_secret)

@st.cache_data(ttl=15)
def get_price(code):
    clean_code = str(code).split('.')[0].zfill(6)
    
    # 1. API 시도
    if token:
        price = get_kis_price(clean_code, input_key, input_secret, token)
        if price: return price
    
    # 2. 크롤링 시도 (API 실패 혹은 키 없을 때)
    try:
        url = f"https://finance.naver.com/item/main.nhn?code={clean_code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=1.5)
        soup = BeautifulSoup(res.text, "html.parser")
        return int(soup.select_one(".no_today .blind").text.replace(",", ""))
    except:
        return 0

# -------------------------------
# 📊 7. 포트폴리오 계산 (이미지 image_2802c1.png 순서 반영)
# -------------------------------
portfolio = {}
try:
    for _, row in df.iterrows():
        # 이미지 순서: [0]날짜, [1]종목, [2]수량, [3]가격, [4]구분, [5]코드
        name = str(row.iloc[1]).strip() if pd.notnull(row.iloc[1]) else ""
        if not name or name == "nan": continue
        
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4]).strip()
        code = str(row.iloc[5]).split('.')[0].zfill(6) if pd.notnull(row.iloc[5]) else ""

        if name not in portfolio:
            portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}

        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * price
        elif action == "매도" and portfolio[name]["qty"] > 0:
            avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
            portfolio[name]["qty"] -= qty
            portfolio[name]["total_buy"] -= avg_p * qty
except Exception as e:
    st.error(f"계산 오류: {e}")

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# -------------------------------
# 📊 8. 결과 집계 및 UI 출력
# -------------------------------
st.title(f"📊 {selected_account} 자산 현황")

if active_stocks:
    result_list = []
    total_eval, total_buy_sum = 0, 0
    
    # 시세 로드
    for name in active_stocks:
        d = portfolio[name]
        curr_p = get_price(d["code"])
        # 수동 가격이 저장되어 있다면 우선 사용
        if db["manual_prices"].get(name):
            curr_p = db["manual_prices"][name]
            
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        total_eval += eval_amt
        total_buy_sum += d["total_buy"]
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        result_list.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])

    total_asset = cash + total_eval
    total_profit_amt = total_eval - total_buy_sum
    total_profit_rate = (total_profit_amt / total_buy_sum * 100) if total_buy_sum > 0 else 0

    # 상단 요약 카드
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("총 자산", f"{int(total_asset):,}원")
    m2.metric("총 평가수익", f"{int(total_profit_amt):+,}원", f"{total_profit_rate:+.2f}%")
    m3.metric("총 평가액", f"{int(total_eval):,}원")

    # 보유 종목 현황 테이블
    st.markdown("### 📋 보유 종목 현황")
    final_rows = []
    for r in result_list:
        weight = (r[4] / total_asset * 100) if total_asset > 0 else 0
        final_rows.append([r[0], r[1], r[2], r[3], r[4], r[5], round(weight, 1)])
    
    # 예수금 행 추가
    cash_weight = (cash / total_asset * 100) if total_asset > 0 else 0
    final_rows.append(["💰 예수금 합계", None, None, None, int(cash), None, round(cash_weight, 1)])
    
    df_res = pd.DataFrame(final_rows, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    # 스타일링
    def color_profit(val):
        if pd.isna(val) or isinstance(val, str): return ""
        color = "#e63946" if val > 0 else "#457b9d" if val < 0 else "black"
        return f"color: {color}; font-weight: bold;"

    st.dataframe(df_res.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}",
        "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-",
        "비중(%)": "{:.1f}%"
    }).map(color_profit, subset=["수익률"]), use_container_width=True)

else:
    st.info("보유 종목이 없습니다. 구글 시트 데이터를 확인하세요.")