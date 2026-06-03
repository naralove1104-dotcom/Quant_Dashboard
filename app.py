import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import date, timedelta

# 페이지 기본 설정
st.set_page_config(page_title="추세추종 퀀트 대시보드", layout="wide")

# 사이드바 설정 (사용자 입력 컨트롤)
st.sidebar.header("백테스트 설정")
ticker = st.sidebar.text_input("종목 티커 (예: SPY, AAPL, 005930.KS)", "SPY")
ma_window = st.sidebar.slider("장기 이평선 기간", 50, 300, 200)
donchian_window = st.sidebar.slider("Donchian 채널 기간 (돌파)", 10, 60, 20)

start_date = st.sidebar.date_input("시작일", date.today() - timedelta(days=365*5))
end_date = st.sidebar.date_input("종료일", date.today())

# 데이터 다운로드 함수 (캐싱 적용으로 속도 최적화)
@st.cache_data
def load_data(ticker, start, end):
    df = yf.download(ticker, start=start, end=end)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# 추세추종 로직 적용 함수
def apply_logic(df, ma_w, donchian_w):
    df = df.copy()
    df['MA'] = df['Close'].rolling(window=ma_w).mean()
    df['Donchian_High'] = df['High'].rolling(window=donchian_w).max().shift(1)
    df['Donchian_Low'] = df['Low'].rolling(window=donchian_w).min().shift(1)

    buy_condition = (df['Close'] > df['MA']) & (df['Close'] >= df['Donchian_High'])
    sell_condition = (df['Close'] < df['MA']) | (df['Close'] < df['Donchian_Low'])

    df['Signal'] = 0
    df.loc[buy_condition, 'Signal'] = 1
    df.loc[sell_condition, 'Signal'] = -1
    
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
    df['Position'] = df['Position'].apply(lambda x: 1 if x == 1 else 0)
    
    df['Daily_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Position'].shift(1) * df['Daily_Return']
    df['Cumulative_Return'] = (1 + df['Strategy_Return']).cumprod()
    
    return df

# 메인 화면 UI 구현
st.title(f"📈 {ticker} 추세추종 백테스트 대시보드")

if st.sidebar.button("데이터 분석 실행"):
    with st.spinner('데이터를 불러오고 계산 중입니다...'):
        # 1. 데이터 로드 및 로직 적용
        raw_data = load_data(ticker, start_date, end_date)
        if raw_data.empty:
            st.error("데이터를 불러오지 못했습니다. 티커를 확인해주세요.")
        else:
            result_df = apply_logic(raw_data, ma_window, donchian_window)
            
            # 2. 핵심 지표 출력
            total_return = (result_df['Cumulative_Return'].iloc[-1] - 1) * 100
            
            col1, col2, col3 = st.columns(3)
            col1.metric("최종 누적 수익률", f"{total_return:.2f}%")
            col2.metric("현재 포지션", "매수 보유 중" if result_df['Position'].iloc[-1] == 1 else "현금 관망")
            col3.metric("현재 200일선 가격", f"{result_df['MA'].iloc[-1]:.2f}")

            # 3. 차트 그리기
            st.subheader("매매 타점 및 추세 시각화")
            fig, ax1 = plt.subplots(figsize=(12, 6))
            
            ax1.plot(result_df.index, result_df['Close'], label='Close Price', alpha=0.5)
            ax1.plot(result_df.index, result_df['MA'], label=f'{ma_window}-day MA', color='orange', linestyle='--')
            
            # 매수 시그널 마커
            buy_signals = result_df[result_df['Signal'] == 1]
            ax1.scatter(buy_signals.index, buy_signals['Close'], marker='^', color='red', s=100, label='Buy Signal')
            
            ax1.legend()
            ax1.grid(True)
            st.pyplot(fig) # Streamlit에 matplotlib 차트 렌더링

            # 4. 최근 시그널 데이터프레임
            st.subheader("최근 시그널 발생 내역 (최근 10일)")
            display_cols = ['Close', 'MA', 'Donchian_High', 'Signal', 'Position']
            st.dataframe(result_df[display_cols].tail(10).style.highlight_max(axis=0))
else:
    st.info("왼쪽 사이드바에서 설정을 마치고 '데이터 분석 실행' 버튼을 눌러주세요.")