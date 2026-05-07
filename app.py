import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="자산 관리 대시보드", layout="wide")

# 2. 구글 시트 데이터 로드 (캐싱 적용)
@st.cache_data(ttl=60)
def load_history_data():
    # secrets.toml에 등록된 spreadsheet_id를 사용합니다.
    spreadsheet_id = "1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw"
    # HISTORY 시트의 GID를 입력하세요 (기본값은 보통 '0'입니다)
    gid = "144293082" 
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    return pd.read_csv(url)

def main():
    try:
        df = load_history_data()
    except Exception as e:
        st.error(f"시트 데이터를 불러오지 못했습니다. 설정(GID 등)을 확인해 주세요: {e}")
        return

    # 쉼표 제거 및 숫자 변환 유틸리티
    def to_num(val):
        if pd.isna(val): return 0
        return pd.to_numeric(str(val).replace(',', ''), errors='coerce') or 0

    # ---------------------------------------------------------
    # 데이터 추출: 사용자님 시트의 2행(누적)과 마지막 행(변동) 사용
    # ---------------------------------------------------------
    # df.iloc[0] : 시트의 2행 (누적수익 행)
    # df.iloc[-1]: 시트의 마지막 행 (최신 기록)
    summary_row = df.iloc[0]
    last_row = df.iloc[-1]
    last_date = last_row.iloc[0] # A열 날짜

    # 사이드바: 계좌 선택
    st.sidebar.header("계좌 필터")
    selected_acc = st.sidebar.selectbox(
        "보고 싶은 항목을 선택하세요", 
        ["전체 합산", "기본 계좌", "한국투자증권"]
    )

    # 선택된 계좌에 따라 시트의 열 인덱스 매칭
    if selected_acc == "기본 계좌":
        cum_profit = to_num(summary_row.iloc[1])    # B2 (기본누적)
        day_diff = to_num(last_row.iloc[4])        # E열 (기본대차)
        week_diff = to_num(last_row.iloc[6])       # G열 (주간변동-기본)
        month_diff = to_num(last_row.iloc[7])      # H열 (월간변동-기본)
    elif selected_acc == "한국투자증권":
        cum_profit = to_num(summary_row.iloc[2])    # C2 (한투누적)
        day_diff = to_num(last_row.iloc[5])        # F열 (한투대차)
        week_diff = to_num(last_row.iloc[8])       # I열 (주간변동-한투)
        month_diff = to_num(last_row.iloc[9])      # J열 (월간변동-한투)
    else: # 전체 합산
        cum_profit = to_num(summary_row.iloc[3])    # D2 (총자산누적)
        day_diff = to_num(last_row.iloc[4]) + to_num(last_row.iloc[5]) # E+F
        week_diff = to_num(last_row.iloc[10])      # K열 (주간변동-합산)
        month_diff = to_num(last_row.iloc[11])     # L열 (월간변동-합산)

    # ---------------------------------------------------------
    # 대시보드 UI 구성
    # ---------------------------------------------------------
    st.title(f"📊 {selected_acc} 리포트")
    st.info(f"📅 데이터 기준일: {last_date}")

    # 1. 상단: 누적 수익 강조 카드
    profit_color = "#e63946" if cum_profit > 0 else "#457b9d" if cum_profit < 0 else "#212529"
    st.markdown(f"""
        <div style="background-color: #f1f3f5; padding: 25px; border-radius: 15px; text-align: center; border: 1px solid #dee2e6; margin-bottom: 20px;">
            <div style="font-size: 1rem; color: #6c757d; font-weight: 600; margin-bottom: 10px;">🎯 누적 투자 수익 (2행 기준)</div>
            <div style="font-size: 2.5rem; font-weight: 800; color: {profit_color};">
                {int(cum_profit):+,} 원
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 2. 하단: 3단 변동 지표
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("전일 대비", f"{int(day_diff):+,} 원", delta=f"{int(day_diff):+,}")
    with col2:
        st.metric("주간 변동 (누적)", f"{int(week_diff):+,} 원", delta=f"{int(week_diff):+,}")
    with col3:
        st.metric("월간 변동 (누적)", f"{int(month_diff):+,} 원", delta=f"{int(month_diff):+,}")

    st.divider()

    # 3. 상세 기록 데이터 (선택 사항)
    with st.expander("📝 최근 상세 기록 확인"):
        # 최신 데이터가 위로 오도록 역순 표시
        st.dataframe(df.iloc[2:].iloc[::-1], use_container_width=True)

if __name__ == "__main__":
    main()