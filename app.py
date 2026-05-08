import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="자산 관리 대시보드", layout="wide")

# 2. 데이터 로드 (캐시 적용)
@st.cache_data(ttl=60)
def load_data():
    # ---------------------------------------------------------
    # 💡 [필독] 아래 spreadsheet_id를 실제 구글 시트 ID로 교체하세요!
    # 시트 주소창 d/ 와 /edit 사이의 문자열입니다.
    # ---------------------------------------------------------
    spreadsheet_id = "1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw" 
    
    # HISTORY 시트의 GID가 0이 아니라면 아래 숫자를 수정하세요.
    gid = "0" 
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.error(f"시트 로드 실패: {e}")
        return pd.DataFrame()

def main():
    df = load_data()
    
    if df.empty:
        st.warning("데이터가 비어 있습니다. 시트 ID와 공유 설정을 확인해 주세요.")
        return

    # 숫자 변환 유틸리티
    def to_num(val):
        if pd.isna(val): return 0
        return pd.to_numeric(str(val).replace(',', ''), errors='coerce') or 0

    # 2행(Index 0) 요약 데이터 추출
    summary = df.iloc[0]

    # 사이드바 설정
    st.sidebar.header("계좌 선택")
    acc = st.sidebar.selectbox("항목", ["기본 계좌", "한국투자증권", "전체 합산"])

    # 계좌별 2행 데이터 매칭 (B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10, L=11)
    if acc == "기본 계좌":
        total = to_num(summary.iloc[1])  # B2
        d = to_num(summary.iloc[4])      # E2
        w = to_num(summary.iloc[6])      # G2
        m = to_num(summary.iloc[7])      # H2
    elif acc == "한국투자증권":
        total = to_num(summary.iloc[2])  # C2
        d = to_num(summary.iloc[5])      # F2
        w = to_num(summary.iloc[8])      # I2
        m = to_num(summary.iloc[9])      # J2
    else: # 전체 합산
        total = to_num(summary.iloc[3])  # D2
        d = to_num(summary.iloc[4]) + to_num(summary.iloc[5])
        w = to_num(summary.iloc[10]) if len(summary) > 10 else 0
        m = to_num(summary.iloc[11]) if len(summary) > 11 else 0

    # 화면 구성
    st.title(f"📊 {acc} 실시간 리포트")
    
    # 메인 수익 카드
    profit_color = "#e63946" if total > 0 else "#457b9d" if total < 0 else "#212529"
    st.markdown(f"""
        <div style="background-color: #ffffff; padding: 25px; border-radius: 15px; text-align: center; border: 1px solid #dee2e6; margin-bottom: 20px;">
            <div style="font-size: 1rem; color: #6c757d; margin-bottom: 10px;">총 누적 투자 수익</div>
            <div style="font-size: 2.8rem; font-weight: 800; color: {profit_color};">
                {int(total):+,} 원
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 3단 변동 지표 (시트 2행 기반)
    c1, c2, c3 = st.columns(3)
    c1.metric("일일 대차", f"{int(d):+,} 원", delta=f"{int(d):+,}")
    c2.metric("주간 대차", f"{int(w):+,} 원", delta=f"{int(w):+,}")
    c3.metric("월간 대차", f"{int(m):+,} 원", delta=f"{int(m):+,}")

    st.divider()

    # 상세 기록 확인 (최신순)
    with st.expander("📝 상세 기록 확인 (최신순)"):
        # 요약행(1행) 제외하고 역순 정렬
        st.dataframe(df.iloc[1:].iloc[::-1], use_container_width=True)

if __name__ == "__main__":
    main()