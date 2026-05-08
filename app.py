import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="자산 관리 대시보드", layout="wide")

# 2. 데이터 로드 (캐시 적용)
@st.cache_data(ttl=60)
def load_data():
    # 💡 [중요] 실제 구글 시트 ID로 교체하세요!
    spreadsheet_id = "1VINP813y8g2d05Y0SZNTgo63jVvIcYHvxJqaZ7D7Kbw" 
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid=0"
    
    try:
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

    # 💡 안전한 숫자 변환 함수 (ValueError 방지)
    def get_safe_num(row, idx):
        try:
            if idx < len(row):
                val = row.iloc[idx]
                if pd.isna(val): return 0
                # 숫자가 아닌 문자(쉼표, 공백 등)를 모두 제거 후 변환
                clean_val = str(val).replace(',', '').replace(' ', '').replace('원', '')
                return int(float(clean_val))
            return 0
        except:
            return 0 # 변환 실패 시 에러 대신 0 반환

    # ---------------------------------------------------------
    # 데이터 추출: 사용자님 시트의 2행(Index 0) 참조
    # ---------------------------------------------------------
    # 만약 첫 번째 데이터 행이 "누적수익"이라는 글자라면 
    # 실제 데이터 위치에 맞게 iloc[0] 또는 iloc[1]을 조정해야 할 수 있습니다.
    summary = df.iloc[0] 

    # 사이드바 계좌 선택
    st.sidebar.header("계좌 선택")
    acc = st.sidebar.selectbox("항목", ["기본 계좌", "한국투자증권", "전체 합산"])

    # 열 인덱스 매칭 (B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10, L=11)
    if acc == "기본 계좌":
        total = get_safe_num(summary, 1)  # B2
        d = get_safe_num(summary, 4)      # E2
        w = get_safe_num(summary, 6)      # G2
        m = get_safe_num(summary, 7)      # H2
    elif acc == "한국투자증권":
        total = get_safe_num(summary, 2)  # C2
        d = get_safe_num(summary, 5)      # F2
        w = get_safe_num(summary, 8)      # I2
        m = get_safe_num(summary, 9)      # J2
    else: # 전체 합산
        total = get_safe_num(summary, 3)  # D2
        d = get_safe_num(summary, 4) + get_safe_num(summary, 5)
        w = get_safe_num(summary, 10)     # K2
        m = get_safe_num(summary, 11)     # L2

    # --- 대시보드 UI ---
    st.title(f"📊 {acc} 리포트")
    
    p_color = "#e63946" if total > 0 else "#457b9d" if total < 0 else "#212529"
    st.markdown(f"""
        <div style="background-color: #ffffff; padding: 25px; border-radius: 15px; text-align: center; border: 1px solid #dee2e6; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 1rem; color: #6c757d; margin-bottom: 10px;">총 누적 투자 수익</div>
            <div style="font-size: 2.8rem; font-weight: 800; color: {p_color};">
                {total:+,} 원
            </div>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("일일 대차", f"{total:+,} 원" if acc=="전체 합산" else f"{d:+,} 원", delta=f"{d:+,}")
    c2.metric("주간 대차", f"{w:+,} 원", delta=f"{w:+,}")
    c3.metric("월간 대차", f"{m:+,} 원", delta=f"{m:+,}")

    st.divider()

    with st.expander("📝 전체 기록 데이터 확인"):
        st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()