import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json

# 시각화 라이브러리 안전하게 로드
try:
    import plotly.graph_objects as go
except ImportError:
    go = None

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
# 📂 3. 구글 시트 정보 설정 및 안전한 로드
# -------------------------------
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {
    "기본 계좌": "0",
    "한국투자증권": "1939408144"
}

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try:
        url = f"{SHEET_BASE}&gid={gid}"
        df = pd.read_csv(url, dtype={'코드': str})
        
        # [핵심] 데이터 타입 강제 통일 및 전처리
        if '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
        
        # 수량과 가격을 숫자로 변환 (숫자가 아닌 것은 NaN이 되고, 0으로 채움)
        for col in ['수량', '가격']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        return df
    except Exception as e:
        st.error(f"⚠️ 시트 로드 실패: {e}")
        return pd.DataFrame()

# -------------------------------
# 📂 4. 사이드바 및 데이터 처리
# -------------------------------
st.sidebar.title("📂 계좌 관리")
selected_account = st.sidebar.selectbox("표시할 계좌를 선택하세요", ["전체 계좌"] + list(TAB_INFO.keys()))

db = load_data()

if st.sidebar.button("🔄 저장된 수동 가격 초기화"):
    db["manual_prices"] = {}
    save_data(db)
    st.rerun()

# 데이터 로드
if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
else:
    df = load_sheet_data(TAB_INFO[selected_account])

if df.empty:
    st.warning("데이터가 없습니다. 구글 시트를 확인해 주세요.")
    st.stop()

# -------------------------------
# 🔹 5. 실시간 시세 크롤링
# -------------------------------
@st.cache_data(ttl=15)
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
# 📊 6. 포트폴리오 계산 (보유 현황)
# -------------------------------
portfolio = {}
for _, row in df.iterrows():
    try:
        name, qty, p, action = row["종목"], float(row["수량"]), float(row["가격"]), row["구분"]
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
# 💹 7. 메인 화면 출력
# -------------------------------
st.title(f"📊 {selected_account}")
price_dict = {}

if active_stocks:
    st.markdown("### 💹 현재 시세 수정")
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

    # 예수금 설정
    acc_key = selected_account if selected_account != "전체 계좌" else "기본 계좌"
    saved_cash = db["cash"].get(acc_key, 1000000)
    cash = st.number_input("💰 현재 예수금 설정", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][acc_key] = cash
        save_data(db)

    # 평가 금액 계산
    result_list = []
    total_eval = 0
    for name in active_stocks:
        d = portfolio[name]
        avg_p = d["total_buy"] / d["qty"]
        curr_p = price_dict[name]
        eval_amt = d["qty"] * curr_p
        total_eval += eval_amt
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        result_list.append([name, d["qty"], int(avg_p), curr_p, int(eval_amt), round(profit_r, 2)])

    total_asset = cash + total_eval
    st.markdown("---")
    st.subheader(f"🏦 총 자산: {int(total_asset):,}원")

    # 보유 종목 테이블
    table_rows = []
    for r in result_list:
        weight = (r[4] / total_asset * 100) if total_asset > 0 else 0
        table_rows.append([r[0], r[1], r[2], r[3], r[4], r[5], round(weight, 1)])
    
    df_final = pd.DataFrame(table_rows, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    def color_profit(val):
        if pd.isna(val) or isinstance(val, str): return ""
        return "color: #e63946; font-weight: bold;" if val > 0 else "color: #457b9d; font-weight: bold;" if val < 0 else ""

    st.dataframe(df_final.style.format({
        "수량": "{:,}", "평단": "{:,}", "현재가": "{:,}", "평가액": "{:,}", "수익률": "{:+.2f}%", "비중(%)": "{:.1f}%"
    }).map(color_profit, subset=["수익률"]), use_container_width=True)

    # -------------------------------
    # 📅 8. 월별 통계 (TypeError 방지 로직 적용)
    # -------------------------------
    if '날짜' in df.columns and not df['날짜'].isnull().all():
        st.markdown("---")
        st.subheader("📅 월별 투자 성과")
        
        stat_df = df.copy()
        stat_df['월'] = stat_df['날짜'].dt.strftime('%Y-%m')
        stat_df = stat_df.dropna(subset=['월'])
        
        monthly_summary = []
        for m in sorted(stat_df['월'].unique()):
            m_df = stat_df[stat_df['월'] == m].copy()
            
            # 수량과 가격을 다시 한번 강제로 float로 변환하여 계산
            m_df['수량'] = pd.to_numeric(m_df['수량'], errors='coerce').fillna(0).astype(float)
            m_df['가격'] = pd.to_numeric(m_df['가격'], errors='coerce').fillna(0).astype(float)
            
            buy_mask = m_df['구분'] == '매수'
            sell_mask = m_df['구분'] == '매도'
            
            m_buy = (m_df.loc[buy_mask, '수량'] * m_df.loc[buy_mask, '가격']).sum()
            m_sell = (m_df.loc[sell_mask, '수량'] * m_df.loc[sell_mask, '가격']).sum()
            
            monthly_summary.append({
                "월": m, 
                "매수금액": int(m_buy), 
                "매도금액": int(m_sell), 
                "순투자": int(m_buy - m_sell)
            })

        if monthly_summary:
            mon_df = pd.DataFrame(monthly_summary)
            if go:
                fig = go.Figure(data=[go.Bar(x=mon_df['월'], y=mon_df['매수금액'], marker_color='#e63946', name='매수액')])
                fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(mon_df.set_index('월')['매수금액'])
            
            st.table(mon_df.style.format("{:,}원", subset=["매수금액", "매도금액", "순투자"]))
else:
    st.info("보유 종목이 없습니다. 구글 시트에 매매 내역을 입력해 주세요.")