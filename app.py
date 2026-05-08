import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="자산 관리 대시보드", layout="wide")

# 2. 데이터 로드 (캐시 적용)
@st.cache_data(ttl=60)
def load_data():
    # 💡 [필독] 실제 구글 시트 ID로 교체하세요! (주소창의 d/ 와 /edit 사이 값)
    spreadsheet_id = "1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw" 
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid=0"
    
    try:
        # 데이터 로드 시 빈 칸이 있어도 모든 열을 유지하도록 읽어옵니다.
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"시트 로드 실패: {e}")
        return pd.DataFrame()

def main():
    df = load_data()
    
    if df.empty:
        st.warning("데이터를 불러오지 못했습니다. 시트 ID와 공유 설정을 확인해 주세요.")
        return

    # ---------------------------------------------------------
    # 💡 안전한 숫자 추출 함수 (IndexError 방지 버전)
    # ---------------------------------------------------------
    def get_val(row, idx):
        if idx < len(row): # 존재하는 인덱스인지 확인
            val = row.iloc[idx]
            if pd.isna(val): return 0
            return pd.to_numeric(str(val).replace(',', ''), errors='coerce') or 0
        return 0 # 칸이 없으면 0 반환

    # 사용자님 설정: 2행(Index 0)은 요약 정보
    summary = df.iloc[0]

    # 사이드바 계좌 선택
    st.sidebar.header("계좌 선택")
    acc = st.sidebar.selectbox("항목", ["기본 계좌", "한국투자증권", "전체 합산"])

    # 계좌별 2행 데이터 매칭 (B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10, L=11)
    if acc == "기본 계좌":
        total = get_val(summary, 1)  # B2
        d = get_val(summary, 4)      # E2
        w = get_val(summary, 6)      # G2
        m = get_val(summary, 7)      # H2
    elif acc == "한국투자증권":
        total = get_val(summary, 2)  # C2
        d = get_val(summary, 5)      # F2
        w = get_val(summary, 8)      # I2
        m = get_val(summary, 9)      # J2
    else: # 전체 합산
        total = get_val(summary, 3)  # D2
        d = get_val(summary, 4) + get_val(summary, 5)
        w = get_val(summary, 10)     # K2
        m = get_val(summary, 11)     # L2

    # --- 화면 구성 ---
    st.title(f"📊 {acc} 리포트")
    
    p_color = "#e63946" if total > 0 else "#457b9d" if total < 0 else "#212529"
    st.markdown(f"""
        <div style="background-color: #ffffff; padding: 25px; border-radius: 15px; text-align: center; border: 1px solid #dee2e6; margin-bottom: 20px;">
            <div style="font-size: 1rem; color: #6c757d; margin-bottom: 10px;">총 누적 투자 수익</div>
            <div style="font-size: 2.8rem; font-weight: 800; color: {p_color};">
                {int(total):+,} 원
            </div>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("일일 대차", f"{int(d):+,} 원", delta=f"{int(d):+,}")
    c2.metric("주간 대차", f"{int(w):+,} 원", delta=f"{int(w):+,}")
    c3.metric("월간 대차", f"{int(m):+,} 원", delta=f"{int(m):+,}")

    st.divider()

    with st.expander("📝 상세 기록 확인"):
        # 요약행 제외하고 표시
        st.dataframe(df.iloc[1:].iloc[::-1], use_container_width=True)

if __name__ == "__main__":
    main()