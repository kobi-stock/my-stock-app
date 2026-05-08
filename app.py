import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="자산 관리 대시보드", layout="wide")

# 2. 데이터 로드 (캐싱 적용)
@st.cache_data(ttl=60)
def load_history_data():
    # 💡 [필독] 본인의 구글 시트 ID를 아래 따옴표 안에 정확히 넣어주세요.
    spreadsheet_id = "1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw" 
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid=0"
    
    try:
        # 빈 칸이 있어도 열 구조를 최대한 유지하며 읽어옵니다.
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

def main():
    df = load_history_data()
    
    if df.empty:
        st.warning("데이터를 불러오지 못했습니다. 시트 ID와 공유 설정을 확인해 주세요.")
        return

    # 💡 [핵심] IndexError와 0 표시 문제를 동시에 해결하는 안전 함수
    def get_val(row, col_idx):
        try:
            # 열 범위를 벗어나면 에러 대신 0 반환 (IndexError 방지)
            if col_idx >= len(row):
                return 0
            val = row.iloc[col_idx]
            if pd.isna(val): return 0
            # 쉼표, 공백, '원' 등을 제거 후 숫자로 강제 변환 (0 표시 방지)
            clean_val = str(val).replace(',', '').replace(' ', '').replace('원', '')
            return int(float(clean_val))
        except:
            return 0

    # 시트의 2행(Index 0)을 요약 데이터로 사용
    summary_row = df.iloc[0]

    # 사이드바 계좌 선택
    st.sidebar.header("계좌 필터")
    acc = st.sidebar.selectbox("항목 선택", ["기본 계좌", "한국투자증권", "전체 합산"])

    # 사용자님 지정 위치 매칭 (B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10, L=11)
    if acc == "기본 계좌":
        cum_p = get_val(summary_row, 1)   # B2
        day_d = get_val(summary_row, 4)   # E2
        week_d = get_val(summary_row, 6)  # G2
        mon_d = get_val(summary_row, 7)   # H2
    elif acc == "한국투자증권":
        cum_p = get_val(summary_row, 2)   # C2
        day_d = get_val(summary_row, 5)   # F2
        week_d = get_val(summary_row, 8)  # I2
        mon_d = get_val(summary_row, 9)   # J2
    else: # 전체 합산
        cum_p = get_val(summary_row, 3)   # D2
        day_d = get_val(summary_row, 4) + get_val(summary_row, 5)
        week_d = get_val(summary_row, 10) # K2
        mon_d = get_val(summary_row, 11)  # L2

    # --- UI 구성 (기존 스타일 복구) ---
    st.title(f"📊 {acc} 리포트")
    
    p_color = "#e63946" if cum_p > 0 else "#457b9d" if cum_p < 0 else "#212529"
    st.markdown(f"""
        <div style="background-color: #ffffff; padding: 30px; border-radius: 15px; text-align: center; border: 1px solid #dee2e6; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p style="margin: 0; font-size: 1.1rem; color: #6c757d; font-weight: 600;">총 누적 투자 수익</p>
            <h1 style="margin: 10px 0; font-size: 3rem; color: {p_color};">{cum_p:+,} 원</h1>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("일일 대차", f"{day_d:+,} 원", delta=f"{day_d:+,}")
    c2.metric("주간 대차", f"{week_d:+,} 원", delta=f"{week_d:+,}")
    c3.metric("월간 대차", f"{mon_d:+,} 원", delta=f"{mon_d:+,}")

    st.divider()
    
    with st.expander("📝 전체 데이터 확인"):
        st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()