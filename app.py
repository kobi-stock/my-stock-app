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
            return {"cash": {}, "manual_prices": {}}
    return {"cash": {}, "manual_prices": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# -------------------------------
# 📱 2. 화면 설정
# -------------------------------
st.set_page_config(page_title="주식 포트폴리오", layout="centered")
st.markdown("""
<style>
.main .block-container { max-width: 900px; padding-top: 2rem; }
div.stNumberInput > label { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# 📂 3. 구글 시트 설정 (URL 수정 금지)
# -------------------------------
# 공유된 시트의 기본 URL
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"

# 각 탭의 GID (시트 하단 탭을 누를 때 주소창 끝에 나오는 숫자)
TAB_INFO = {
    "기본 계좌": "0",
    "한국투자증권": "1939408144"
}

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try:
        url = f"{SHEET_BASE}&gid={gid}"
        df = pd.read_csv(url)
        # 데이터 전처리: 수량/가격을 숫자로 강제 변환
        for col in ['수량', '가격']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"⚠️ 시트 로드 중 오류 발생: {e}")
        return pd.DataFrame()

st.sidebar.title("📂 계좌 관리")
selected_account = st.sidebar.selectbox("계좌를 선택하세요", ["전체 계좌"] + list(TAB_INFO.keys()))
db = load_data()

# -------------------------------
# 📂 4. 데이터 로드 (구글 시트 연동)
# -------------------------------
if selected_account == "전체 계좌":
    dfs = [load_sheet_data(gid) for gid in TAB_INFO.values()]
    df = pd.concat(dfs, ignore_index=True) if any(not d.empty for d in dfs) else pd.DataFrame()
else:
    df = load_sheet_data(TAB_INFO[selected_account])

if df.empty:
    st.info("구글 시트 데이터를 가져올 수 없습니다. 공유 설정을 확인하세요.")
    st.stop()

# 🔍 데이터 확인용 (필요할 때 열어서 확인)
with st.expander("📝 시트 데이터 원본 확인"):
    st.write(df)

st.title(f"📊 {selected_account} 포트폴리오")

# -------------------------------
# 💰 5. 예수금 처리
# -------------------------------
if selected_account == "전체 계좌":
    cash = sum([db["cash"].get(acc, 1000000) for acc in TAB_INFO.keys()])
    st.info(f"💡 합산 예수금: {cash:,}원 (개별 계좌 화면에서 수정 가능)")
else:
    saved_cash = db["cash"].get(selected_account, 1000000)
    cash = st.number_input(f"💰 {selected_account} 예수금 설정", value=int(saved_cash), step=10000)
    if cash != saved_cash:
        db["cash"][selected_account] = cash
        save_data(db)

# -------------------------------
# 🔹 6. 시세 크롤링 함수
# -------------------------------
@st.cache_data(ttl=15)
def get_price(code):
    if not code or str(code) == 'nan': return 0
    try:
        # 코드를 6자리 문자열로 포맷팅
        code_str = str(code).split('.')[0].zfill(6)
        url = f"https://finance.naver.com/item/main.nhn?code={code_str}"
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        price_tag = soup.select_one(".no_today .blind")
        return int(price_tag.text.replace(",", "")) if price_tag else 0
    except:
        return 0

# -------------------------------
# 📊 7. 포트폴리오 계산 logic
# -------------------------------
portfolio = {}
for _, row in df.iterrows():
    try:
        name, qty, p, action = row["종목"], row["수량"], row["가격"], row["구분"]
        code = str(row["코드"]).split('.')[0].zfill(6)
        
        if name not in portfolio: 
            portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
            
        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * p
        elif action == "매도":
            if portfolio[name]["qty"] > 0:
                avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
                portfolio[name]["qty"] -= qty
                portfolio[name]["total_buy"] -= avg_p * qty
    except:
        continue

active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# -------------------------------
# 💹 8. 현재가 입력 및 저장
# -------------------------------
st.markdown("### 💹 실시간 시세 (수동 입력 시 저장)")
price_dict = {}
if active_stocks:
    cols = st.columns(4)
    for i, name in enumerate(active_stocks):
        data = portfolio[name]
        saved_p = db["manual_prices"].get(name)
        auto_p = get_price(data["code"])
        
        # 기본값 설정
        init_val = saved_p if saved_p else (auto_p if auto_p > 0 else int(data["total_buy"]/data["qty"]))
        
        with cols[i % 4]:
            p_input = st.number_input(f"{name} ({auto_p:,})", value=int(init_val), key=f"inp_{name}")
            if p_input != saved_p:
                db["manual_prices"][name] = p_input
                save_data(db)
            price_dict[name] = p_input
else:
    st.write("보유 중인 종목이 없습니다.")

# -------------------------------
# 📊 9. 최종 집계 및 화면 출력
# -------------------------------
result_list = []
total_eval, total_buy = 0, 0

for name in active_stocks:
    d = portfolio[name]
    avg_p = d["total_buy"] / d["qty"]
    curr_p = price_dict[name]
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
st.markdown("### 📊 계좌 요약")
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
    "평가액": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
    "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-",
    "비중(%)": lambda x: f"{x:.1f}%" if pd.notnull(x) else "0.0%"
}).map(color_p, subset=['수익률']).set_properties(**{'text-align': 'right'}), use_container_width=True)