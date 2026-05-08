import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="자산 관리 대시보드", layout="wide")

# 2. 구글 시트 데이터 로드 (캐싱 적용: 60초마다 갱신)
@st.cache_data(ttl=60)
def load_history_data():
    try:
        # 💡 이곳에 사용자님의 실제 구글 시트 ID를 직접 입력하세요.
        spreadsheet_id = "1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw"
        gid = "0" 
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
        return pd.read_csv(url)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

def main():
    df = load_history_data()
    
    if df.empty:
        st.warning("시트에서 데이터를 불러올 수 없습니다. 시트 ID와 공유 설정을 확인해 주세요.")
        return

    # 💡 [보강] 숫자가 아닌 문자(쉼표, 빈칸 등)를 강제로 숫자로 변환하는 함수
    def to_num(val):
        try:
            if pd.isna(val): return 0
            # 쉼표, 공백, '원' 표시 등을 모두 제거 후 변환
            clean_val = str(val).replace(',', '').replace(' ', '').replace('원', '')
            return int(float(clean_val))
        except:
            return 0

    # ---------------------------------------------------------
    # 데이터 추출: 시트의 2행(Index 0) 요약 데이터 참조
    # ---------------------------------------------------------
    summary_row = df.iloc[0]

    # 사이드바: 계좌 선택
    st.sidebar.header("계좌 필터")
    selected_acc = st.sidebar.selectbox(
        "보고 싶은 항목을 선택하세요", 
        ["기본 계좌", "한국투자증권", "전체 합산"]
    )

    # 💡 [수정] 대차 데이터 추출 로직 (E2, G2, H2 등 지정 위치)
    if selected_acc == "기본 계좌":
        cum_profit = to_num(summary_row.iloc[1])    # B2
        day_diff = to_num(summary_row.iloc[4])      # E2 (기본일일)
        week_diff = to_num(summary_row.iloc[6])     # G2 (기본주간)
        month_diff = to_num(summary_row.iloc[7])    # H2 (기본월간)
    elif selected_acc == "한국투자증권":
        cum_profit = to_num(summary_row.iloc[2])    # C2
        day_diff = to_num(summary_row.iloc[5])      # F2 (한투일일)
        week_diff = to_num(summary_row.iloc[8])     # I2 (한투주간)
        month_diff = to_num(summary_row.iloc[9])    # J2 (한투월간)
    else: # 전체 합산
        cum_profit = to_num(summary_row.iloc[3])    # D2
        day_diff = to_num(summary_row.iloc[4]) + to_num(summary_row.iloc[5])
        week_diff = to_num(summary_row.iloc[10]) if len(summary_row) > 10 else 0
        month_diff = to_num(summary_row.iloc[11]) if len(summary_row) > 11 else 0

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
    
    # 3. 상세 기록 확인
    with st.expander("📝 최근 데이터 상세 보기"):
        st.dataframe(df.iloc[::-1], use_container_width=True)

if __name__ == "__main__":
    main()