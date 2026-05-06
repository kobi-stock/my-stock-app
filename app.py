import pandas as pd
import streamlit as st
import requests
import datetime
import re

# 📱 1. 화면 설정 및 스타일
st.set_page_config(page_title="주식 포트폴리오", layout="centered")

st.markdown("""
<style>
    h1 { font-size: 1.5rem !important; }
    h3 { font-size: 1.1rem !important; }
    .card-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-start; margin-bottom: 15px; }
    .custom-card {
        background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px;
        padding: 10px; min-width: 100px; flex: 1 1 calc(33.3% - 8px);
        box-shadow: 1px 1px 3px rgba(0,0,0,0.05); text-align: center;
    }
    @media (max-width: 480px) { .custom-card { flex: 1 1 calc(50% - 8px); } }
    .card-label { font-size: 0.75rem; color: #6c757d; margin-bottom: 4px; }
    .card-value { font-size: 0.95rem; font-weight: 700; color: #212529; }
    .card-delta { font-size: 0.75rem; font-weight: 600; margin-top: 2px; }
    .up { color: #e63946 !important; }
    .down { color: #457b9d !important; }
</style>
""", unsafe_allow_html=True)

# 💹 2. 실시간 시세 엔진
@st.cache_data(ttl=5)
def get_live_price(code):
    if not code or pd.isna(code) or str(code).strip() == "" or code == "None": return 0
    clean_code = re.sub(r'[^0-9]', '', str(code)).zfill(6)
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{clean_code}"
        res = requests.get(url, timeout=2).json()
        return int(res['result']['areas'][0]['datas'][0]['nv'])
    except: return 0

# 📂 3. 구글 시트 데이터 로드
SHEET_BASE = "https://docs.google.com/spreadsheets/d/1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw/export?format=csv"
TAB_INFO = {"기본 계좌": "0", "한국투자증권": "1939408144"}

@st.cache_data(ttl=10)
def load_sheet_data(gid):
    try: return pd.read_csv(f"{SHEET_BASE}&gid={gid}", dtype=str)
    except: return pd.DataFrame()

# 🔐 사이드바 설정
st.sidebar.title("🔐 계좌 설정")
selected_account = st.sidebar.selectbox("대상 계좌 선택", ["전체 계좌"] + list(TAB_INFO.keys()))

all_dfs = []
if selected_account == "전체 계좌":
    for gid in TAB_INFO.values():
        all_dfs.append(load_sheet_data(gid))
else:
    all_dfs.append(load_sheet_data(TAB_INFO[selected_account]))

df_raw = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

# 데이터 처리 변수 초기화
portfolio = {}
cash_list = [] # 모든 예수금 기록을 담을 리스트
history_data = {} # {날짜: 총잔고}

if not df_raw.empty:
    for _, row in df_raw.iterrows():
        date_val = str(row.iloc[0]).strip()
        name = str(row.iloc[1]).strip()
        qty = pd.to_numeric(str(row.iloc[2]).replace(',', ''), errors='coerce') or 0
        price = pd.to_numeric(str(row.iloc[3]).replace(',', ''), errors='coerce') or 0
        action = str(row.iloc[4]).strip()
        code = str(row.iloc[5]).strip()

        if not name or name == "nan" or name == "종목": continue

        # [수정: 예수금 합산 방지] 예수금이라는 이름이 있으면 리스트에 추가 (나중에 마지막 값만 사용)
        if "예수금" in name:
            cash_list.append(price)
            continue
        # [수정: 총잔고 분리] 총잔고 기록은 히스토리 데이터로만 활용
        if "총잔고" in name:
            history_data[date_val] = price
            continue

        # [주식 포트폴리오 계산]
        if name not in portfolio: portfolio[name] = {"qty": 0, "total_buy": 0, "code": code}
        if action == "매수":
            portfolio[name]["qty"] += qty
            portfolio[name]["total_buy"] += qty * price
        elif action == "매도" and portfolio[name]["qty"] > 0:
            avg_p = portfolio[name]["total_buy"] / portfolio[name]["qty"]
            portfolio[name]["qty"] -= qty
            portfolio[name]["total_buy"] -= avg_p * qty

# 최종 예수금 결정 (리스트의 가장 마지막 값 사용)
total_cash = cash_list[-1] if cash_list else 0
active_stocks = [n for n, d in portfolio.items() if d["qty"] > 0]

# 4️⃣ 메인 화면 출력
st.title(f"📊 {selected_account}")

if active_stocks or total_cash > 0:
    # 실시간 시세 카드
    price_dict = {}
    if active_stocks:
        st.subheader("💹 실시간 종목 시세")
        stock_html = '<div class="card-container">'
        for name in active_stocks:
            live_p = get_live_price(portfolio[name]["code"])
            price_dict[name] = live_p
            stock_html += f'<div class="custom-card"><div class="card-label">{name}</div><div class="card-value">{live_p:,}</div></div>'
        stock_html += '</div>'
        st.markdown(stock_html, unsafe_allow_html=True)

    # 자산 데이터 계산
    total_eval, total_buy_sum, result_list = 0, 0, []
    for name in active_stocks:
        d = portfolio[name]
        curr_p = price_dict.get(name, 0)
        avg_p = d["total_buy"] / d["qty"]
        eval_amt = d["qty"] * curr_p
        total_eval += eval_amt
        total_buy_sum += d["total_buy"]
        profit_r = (curr_p - avg_p) / avg_p * 100 if avg_p else 0
        result_list.append([name, d["qty"], int(avg_p), int(curr_p), int(eval_amt), round(profit_r, 2)])

    total_asset = total_cash + total_eval

    # 5️⃣ 계좌 변동 및 요약 (전일대비 등)
    st.divider()
    st.subheader("📈 계좌 변동 및 요약")
    
    def get_comparison(days):
        target_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        past_dates = sorted([d for d in history_data.keys() if d <= target_date], reverse=True)
        if not past_dates: return 0, 0.0
        past_val = history_data[past_dates[0]]
        diff = total_asset - past_val
        return diff, (diff / past_val * 100) if past_val != 0 else 0

    d_val, d_rate = get_comparison(1)
    w_val, w_rate = get_comparison(7)
    m_val, m_rate = get_comparison(30)
    t_profit_amt = total_eval - total_buy_sum
    t_profit_rate = (t_profit_amt / total_buy_sum * 100) if total_buy_sum > 0 else 0

    metrics_html = '<div class="card-container">'
    for label, val, rate in [("전일대비", d_val, d_rate), ("전주대비", w_val, w_rate), ("전월대비", m_val, m_rate)]:
        cls = "up" if val > 0 else "down" if val < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(val):+,}</div><div class="card-delta {cls}">{rate:+.2f}%</div></div>'
    
    summary = [("💰 예수금", total_cash, ""), ("📥 총매수액", total_buy_sum, ""), ("🏦 총자산", total_asset, ""), ("📊 총수익률", t_profit_amt, f"{t_profit_rate:+.2f}%")]
    for label, val, rate_str in summary:
        cls = "up" if "수익률" in label and val > 0 else "down" if "수익률" in label and val < 0 else ""
        metrics_html += f'<div class="custom-card"><div class="card-label">{label}</div><div class="card-value">{int(val):,}</div><div class="card-delta {cls}">{rate_str}</div></div>'
    metrics_html += '</div>'
    st.markdown(metrics_html, unsafe_allow_html=True)

    # 6️⃣ 보유 종목 리스트
    st.divider()
    st.subheader("📋 보유 종목 리스트")
    final_data = [[r[0], r[1], r[2], r[3], r[4], r[5], round(r[4]/total_asset*100, 1)] for r in result_list]
    final_data.append(["💰 예수금", None, None, None, int(total_cash), None, round(total_cash/total_asset*100, 1)])
    df_final = pd.DataFrame(final_data, columns=["종목", "수량", "평단", "현재가", "평가액", "수익률", "비중(%)"])
    
    def style_profit(val):
        if val is None or isinstance(val, str): return ''
        color = '#e63946' if val > 0 else '#457b9d' if val < 0 else '#212529'
        return f'color: {color}; font-weight: bold;'

    st.dataframe(df_final.style.format({
        "수량": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평단": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "현재가": lambda x: f"{int(x):,}" if pd.notnull(x) else "-",
        "평가액": "{:,.0f}", "수익률": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-", "비중(%)": "{:.1f}%"
    }).map(style_profit, subset=['수익률']), use_container_width=True, hide_index=True)

else:
    st.info("시트에 데이터를 입력해주세요. (주식 종목 혹은 '예수금' 항목)")