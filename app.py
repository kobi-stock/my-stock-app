import streamlit as st
import pandas as pd

# 1. 페이지 기본 설정
st.set_page_config(page_title="주식 투자 대시보드", layout="wide")

# 2. 구글 시트 데이터 로드 함수
@st.cache_data(ttl=60)  # 1분마다 새 데이터를 가져옴
def load_data():
    # secrets.toml에 등록된 spreadsheet_id와 HISTORY 시트의 GID를 사용합니다.
    spreadsheet_id = st.secrets["gsheets"]["spreadsheet_id"]
    gid = "0"  # HISTORY 시트의 GID (실제 GID로 확인 필요)
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    return pd.read_csv(url)

def main():
    try:
        df = load_data()
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return

    # 숫자 변환 함수 (쉼표 제거 및 에러 처리)
    def to_num(val):
        if pd.isna(val): return 0
        return pd.to_numeric(str(val).replace(',', ''), errors='coerce') or 0

    # ---------------------------------------------------------
    # 데이터 추출 (사용자님의 시트 구조 반영)
    # ---------------------------------------------------------
    # df.iloc[0] = 시트의 2행 (누적수익 행)
    # df.iloc[-1] = 시트의 마지막 행 (최신 기록 행)
    
    summary_row = df.iloc[0]
    last_row = df.iloc[-1]

    # 사이드바에서 계좌 선택
    st.sidebar.header("계좌 설정")
    selected_acc = st.sidebar.selectbox("보고 싶은 계좌를 선택하세요", ["전체 합산", "기본 계좌", "한국투자증권"])

    # 계좌별 데이터 매칭 (시트의 열 인덱스 기준)
    if selected_acc == "기본 계좌":
        # B(1), E(4), G(6), H(7) 열 참조
        cum_total = to_num(summary_row.iloc[1])    # 누적수익(B2)
        daily_diff = to_num(last_row.iloc[4])      # 기본대차(E)
        weekly_diff = to_num(last_row.iloc[6])     # 주간변동-기본(G)
        monthly_diff = to_num(last_row.iloc[7])    # 월간변동-기본(H)
    elif selected_acc == "한국투자증권":
        # C(2), F(5), I(8), J(9) 열 참조
        cum_total = to_num(summary_row.iloc[2])    # 누적수익(C2)
        daily_diff = to_num(last_row.iloc[5])      # 한투대차(F)
        weekly_diff = to_num(last_row.iloc[8])     # 주간변동-한투(I)
        monthly_diff = to_num(last_row.iloc[9])    # 월간변동-한투(J)
    else:
        # D(3), E+F, K(10), L(11) 열 참조
        cum_total = to_num(summary_row.iloc[3])    # 누적수익(D2)
        daily_diff = to_num(last_row.iloc[4]) + to_num(last_row.iloc[5])
        weekly_diff = to_num(last_row.iloc[10])    # 주간변동-합산(K)
        monthly_diff = to_num(last_row.iloc[11])   # 월간변동-합산(L)

    # ---------------------------------------------------------
    # 대시보드 화면 표시
    # ---------------------------------------------------------
    st.title(f"📊 {selected_acc} 투자 리포트")
    st.caption(f"마지막 업데이트: {last_row.iloc[0]}") # A열 날짜 표시

    # 1. 상단 큰 누적 수익 카드
    color = "#e63946" if cum_total > 0 else "#457b9d" if cum_total < 0 else "#212529"
    st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 30px; border-radius: 15px; text-align: center; border: 1px solid #dee2e6; margin-bottom: 25px;">
            <p style="margin: 0; font-size: 1.1rem; color: #6c757d; font-weight: 600;">총 누적 수익 (기준일 이후)</p>
            <h1 style="margin: 10px 0; font-size: 3rem; color: {color};">
                {int(cum_total):+,} 원
            </h1>
        </div>
    """, unsafe_allow_html=True)

    # 2. 하단 3단 변동 지표 (Metric)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("전일 대비", f"{int(daily_diff):+,} 원", delta=f"{int(daily_diff):+,}")
    with col2:
        st.metric("이번 주 변동", f"{int(weekly_diff):+,} 원", delta=f"{int(weekly_diff):+,}")
    with col3:
        st.metric("이번 달 변동", f"{int(monthly_diff):+,} 원", delta=f"{int(monthly_diff):+,}")

    # 3. 데이터 테이블 확인 (선택 사항)
    with st.expander("최근 기록 데이터 보기"):
        st.dataframe(df.tail(10), use_container_width=True)

if __name__ == "__main__":
    main()