import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json
import plotly.graph_objects as go

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
st.set_page_config(page_title="주식 포트폴리오 관리", layout="centered")
st.markdown("""
<style>
.main .block-container { max-width: 850px; padding-top: 2rem; }
div.stNumberInput > label { font-weight: bold; font-size: 13px; }
.stDataFrame { font-size: 14px; }
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

@st.cache_data(ttl=10) # 10초마다 갱신
def load_sheet_data(gid):
    try:
        url = f"{SHEET_BASE}&gid={gid}"
        df = pd.read_csv(url, dtype={'코드': str})
        # 날짜 형식 변환
        if '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"⚠️ 시트 로드 실패: {e}")
        return pd.DataFrame()

# -------------------------------
# 📂 4. 사이드바 및 데이터 로드
# -------------------------------
st.sidebar.title("📂 계좌 관리")
selected_account = st.sidebar.selectbox("표시할 계좌를 선택하세요", ["전체 계좌"] + list(TAB_INFO.keys()))

db = load_data()

if st.sidebar.button("🔄 저장된 수동 가격 초기화"):
    db["manual_prices"] = {}
    save_data(db)
    st.rerun()

# 데이터 통합 로드
if selected_account == "전체 계좌":
    dfs = []
    for gid in TAB_INFO.values():
        temp = load_sheet_data(gid)
        if not temp.empty: dfs.append(temp)
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
else:
    df = load_sheet_data(TAB_INFO[selected_account])

if df.empty:
    st.warning("데이터가 없습니다. 구글 시트 공유 설정과 날짜 형식을 확인해 주세요.")
    st.stop()

# -------------------------------
# 🔹 5. 실시간 시세 크롤링
# -------------------------------
@st.cache_data(ttl=20)
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
# 📊 6. 포트폴리오 계산
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
st.title(f"📊 {selected_account}")
price_dict = {}

if active_stocks:
    cols = st.columns(3)
    for i, name in enumerate(active_stocks):
        data = portfolio[name]
        live_p = get_live_price(data["code"])
        saved_p = db["manual_prices"].get(name)
        display_val = saved_p if saved_p else live_p
        
        with cols[i % 3]:
            p_input = st.number_input(f"{name} ({live_p:,})", value=int(display_val), key=f"p_{name}")
            if p_input != saved_p and p_input != live_p:
                db["manual_prices"][name] = p_input
                save_data(db)
            price_dict[name] = p_input

    # -------------------------------
    # 💰 8. 요약 통계 및 테이블 (기존 동일)
    # -------------------------------
    saved_cash = db["cash"].get(selected_account if selected_account != "전체 계좌" else "기본 계좌", 1000000)
    cash = saved_cash if selected_account == "전체 계좌" else st.number_input("💰 예수금 설정", value=int(saved_cash))
    if selected_account != "전체 계좌" and cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

    # ... 자산 계산 생략 ...
    total_buy = sum([d["total_buy"] for d in portfolio.values()])
    total_eval = sum([portfolio[name]["qty"] * price_dict[name] for name in active_stocks])
    total_asset = cash + total_eval
    
    st.markdown(f"### 🏦 총 자산: {int(total_asset):,}원")

    # -------------------------------
    # 📅 9. 월별 통계 분석 (핵심 추가)
    # -------------------------------
    st.markdown("---")
    st.subheader("📅 월별 투자 성과")

    if '날짜' in df.columns and not df['날짜'].isnull().all():
        df['월'] = df['날짜'].dt.strftime('%Y-%m')
        
        # 월별 매수/매도 합계 계산
        monthly_data = []
        months = sorted(df['월'].unique())
        
        cumulative_invested = 0
        for m in months:
            m_df = df[df['월'] == m]
            m_buy = (m_df[m_df['구분'] == '매수']['수량'] * m_df[m_df['구분'] == '매수']['가격']).sum()
            m_sell = (m_df[m_df['구분'] == '매도']['수량'] * m_df[m_df['구분'] == '매도']['가격']).sum()
            
            # 월별 수익금액 (간이 계산: 매도 - 매수)
            m_profit_amt = m_sell - m_buy
            m_profit_rate = (m_profit_amt / m_buy * 100) if m_buy > 0 else 0
            
            monthly_data.append({
                "월": m,
                "매수금액": int(m_buy),
                "매도금액": int(m_sell),
                "수익률": round(m_profit_rate, 2),
                "순투자액": int(m_buy - m_sell)
            })

        mon_df = pd.DataFrame(monthly_data)
        
        # 월별 수익률 차트
        fig = go.Figure()
        fig.add_trace(go.Bar(x=mon_df['월'], y=mon_df['수익률'], name='월별 수익률(%)',
                             marker_color=['#e63946' if x > 0 else '#457b9d' for x in mon_df['수익률']]))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

        # 월별 요약 테이블
        st.dataframe(mon_df.style.format({
            "매수금액": "{:,}원",
            "매도금액": "{:,}원",
            "수익률": "{:+.2f}%",
            "순투자액": "{:,}원"
        }), use_container_width=True)

    else:
        st.info("월별 통계를 보려면 구글 시트에 '날짜' 데이터를 입력해 주세요.")