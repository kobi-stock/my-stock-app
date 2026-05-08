import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="자산 관리 대시보드", layout="wide")

# 2. 구글 시트 데이터 로드 (캐싱 적용: 60초마다 갱신)
@st.cache_data(ttl=60)
def load_history_data():
    # ---------------------------------------------------------
    # 💡 [필독] 아래 따옴표 안에 실제 구글 시트 ID를 입력하세요!
    # 주소창의 /d/ 와 /edit 사이의 복잡한 문자열입니다.
    # ---------------------------------------------------------
    spreadsheet_id = "1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw" 
    
    # HISTORY 시트의 GID (보통 첫 번째 시트는 0)
    gid = "0" 
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

def main():
    df = load_history_data()
    
    if df.empty:
        st.warning("시트에서 데이터를 불러올 수 없습니다. 시트 ID와 공유 설정(링크가 있는 모든 사용자에게 뷰어 권한)을 확인해 주세요.")
        return

    # 💡 숫자가 아닌 텍스트나 빈 칸을 안전하게 처리하는 함수
    def get_safe_num(row, idx):
        try:
            if idx < len(row):
                val = row.iloc[idx]
                if pd.isna(val): return 0
                # 쉼표, 원화 표시, 공백 제거 후 숫자로 변환
                clean_val = str(val).replace(',', '').replace(' ', '').replace('원', '')
                return int(float(clean_val))
            return 0
        except:
            return 0

    # ---------------------------------------------------------
    # 데이터 추출: 사용자님 설정(2행 요약 데이터) 반영
    # ---------------------------------------------------------
    # df.iloc[0]은 시트의 실제 데이터 2행을 의미함
    summary_row = df.iloc[0]

    # 사이드바: 계좌 선택
    st.sidebar.header("계좌 필터")
    selected_acc = st.sidebar.selectbox(
        "보고 싶은 항목을 선택하세요", 
        ["기본 계좌", "한국투자증권", "전체 합산"]
    )

    # 열 위치 매칭 (B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10, L=11)
    if selected_acc == "기본 계좌":
        cum_profit = get_safe_num(summary_row, 1)    # B2
        day_diff = get_safe_num(summary_row, 4)      # E2
        week_diff = get_safe_num(summary_row, 6)     # G2
        month_diff = get_safe_num(summary_row, 7)    # H2
    elif selected_acc == "한국투자증권":
        cum_profit = get_safe_num(summary_row, 2)    # C2
        day_diff = get_safe_num(summary_row, 5)      # F2
        week_diff = get_safe_num(summary_row, 8)     # I2
        month_diff = get_safe_num(summary_row, 9)    # J2
    else: # 전체 합산
        cum_profit = get_safe_num(summary_row, 3)    # D2
        day_diff = get_safe_num(summary_row, 4) + get_safe_num(summary_row, 5) # E2 + F2
        week_diff = get_safe_num(summary_row, 10)    # K2
        month_diff = get_safe_num(summary_row, 11)   # L2

    # ---------------------------------------------------------
    # 대시보드 UI 구성
    # ---------------------------------------------------------
    st.title(f"📊 {selected_acc} 리포트")
    
    # 1. 상단: 누적 수익 카드
    profit_color = "#e63946" if cum_profit > 0 else "#457b9d" if cum_profit < 0 else "#212529"
    st.markdown(f"""
        <div style="background-color: #ffffff; padding: 30px; border-radius: 15px; text-align: center; border: 1px solid #dee2e6; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p style="margin: 0; font-size: 1.1rem; color: #6c757d; font-weight: 600;">총 누적 투자 수익</p>
            <h1 style="margin: 10px 0; font-size: 3rem; color: {profit_color};">
                {int(cum_profit):+,} 원
            </h1>
        </div>
    """, unsafe_allow_html=True)

    # 2. 하단: 3단 변동 지표 (일일/주간/월간 대차)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("일일 대차", f"{int(day_diff):+,} 원", delta=f"{int(day_diff):+,}")
    with col2:
        st.metric("주간 대차", f"{int(week_diff):+,} 원", delta=f"{int(week_diff):+,}")
    with col3:
        st.metric("월간 대차", f"{int(month_diff):+,} 원", delta=f"{int(month_diff):+,}")

    st.divider()
    
    # 3. 상세 기록 확인 (전체 데이터를 최신순으로 표시)
    with st.expander("📝 전체 시트 데이터 상세 보기"):
        st.dataframe(df.iloc[::-1], use_container_width=True)

if __name__ == "__main__":
    main()