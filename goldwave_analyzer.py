import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="GoldWave EA Analyzer", layout="wide", page_icon="📊")

st.title("📊 골드웨이브(GOLDWAVE) EA 통합 대시보드")
st.caption("회원 데이터 정밀 정산 및 실시간 EA 계좌 모니터링 시스템")

# 상단 탭 구성 (은경님 제안 반영)
tab1, tab2 = st.tabs(["📁 회원 엑셀 정산기 (오리지널)", "📡 남편 EA 실시간 모니터링"])

# =========================================================================
# [TAB 1] 회원 엑셀 정산기 (기존 은경님 알고리즘 100% 동일 구역)
# =========================================================================
with tab1:
    st.subheader("🔒 회원 마감용 엑셀 정산 시스템")
    uploaded_file = st.file_uploader("MT5에서 내보낸 회원 엑셀 파일(.xlsx)을 업로드하세요.", type=["xlsx"], key="excel_uploader")

    if uploaded_file is not None:
        try:
            raw_df = pd.read_excel(uploaded_file, header=None)
            
            # --- [은경님's 정산 알고리즘 주입] ---
            credit = 0.0
            for idx, row in raw_df.iterrows():
                if idx > 400 and str(row[0]).startswith("4/1~4/30 받은 크레딧"):
                    credit = float(row[3])
                    break
            if credit == 0.0:
                credit = 1115.05

            start_idx = 295
            columns_row = raw_df.iloc[start_idx].tolist()
            trade_df = raw_df.iloc[start_idx+1:494].copy()
            trade_df.columns = columns_row
            
            trade_df['수익'] = pd.to_numeric(trade_df['수익'], errors='coerce').fillna(0)
            trade_df['수수료'] = pd.to_numeric(trade_df['수수료'], errors='coerce').fillna(0)
            trade_df['스왑'] = pd.to_numeric(trade_df['스왑'], errors='coerce').fillna(0)
            
            init_balance = float(trade_df['잔액'].iloc[0])
            real_start_capital = init_balance + credit
            
            total_profit = trade_df['수익'].sum()
            total_fee = trade_df['수수료'].sum()
            total_net_profit = total_profit + total_fee
            
            real_return_rate = (total_net_profit / real_start_capital) * 100
            
            # 화면 출력
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("실질 기준 자본금 (이월+크레딧)", f"${real_start_capital:,.2f}")
            col2.metric("유지 중인 신용편의(크레딧)", f"${credit:,.2f}")
            col3.metric("당월 누적 총수입 (Net)", f"${total_net_profit:,.2f}", delta=f"${total_profit:,.2f} 수익")
            col4.metric("실질 월간 수익률 (%)", f"{real_return_rate:.2f}%")

            # 패턴 진단
            st.markdown("---")
            st.subheader("🔍 종목 및 EA 전략별 성과 분석 (패턴 진단)")
            closed_trades = trade_df[trade_df['방향'] == 'out'].copy()
            closed_trades['비고'] = closed_trades['비고'].fillna('일반매매')
            
            summary_list = []
            for (symbol, strategy), group in closed_trades.groupby(['통화', '비고']):
                total_cnt = len(group)
                win_cnt = len(group[group['수익'] > 0])
                win_rate = (win_cnt / total_cnt) * 100 if total_cnt > 0 else 0
                pos_profit = group[group['수익'] > 0]['수익'].sum()
                neg_loss = abs(group[group['수익'] < 0]['수익'].sum())
                profit_factor = (pos_profit / neg_loss) if neg_loss > 0 else pos_profit
                net_p = group['수익'].sum() + group['수수료'].sum()
                
                status = "🔥 주동력 (안정)" if win_rate >= 60 and profit_factor >= 1.5 else "✅ 정상 작동"
                if win_rate < 40 or profit_factor < 1.0:
                    status = "⚠️ 약점 발견 (주의)"
                    
                summary_list.append({
                    "종목": symbol, "적용 로직(세션)": strategy, "총 거래횟수": f"{total_cnt}회",
                    "승률": f"{win_rate:.1f}%", "손익비 (PF)": f"{profit_factor:.2f}",
                    "구간 순수익": f"${net_p:,.2f}", "진단 상태": status
                })
                
            st.dataframe(pd.DataFrame(summary_list), use_container_width=True)

        except Exception as e:
            st.error(f"엑셀 분석 중 오류 발생: {e}")

# =========================================================================
# [TAB 2] 남편 EA 실시간 모니터링 (실시간 데이터 독립 계산 구역)
# =========================================================================
with tab2:
    st.subheader("📡 남편분 PC MT5 실시간 연동 현황")
    
    FIREBASE_URL = None
    try:
        if "FIREBASE_DB_URL" in st.secrets:
            FIREBASE_URL = st.secrets["FIREBASE_DB_URL"]
            if not FIREBASE_URL.endswith(".json"):
                FIREBASE_URL = FIREBASE_URL.rstrip("/") + "/trading_history.json"
    except Exception:
        pass

    fb_df = None
    if FIREBASE_URL:
        try:
            response = requests.get(FIREBASE_URL)
            if response.status_code == 200 and response.json():
                fb_data = response.json()
                fb_df = pd.DataFrame.from_dict(fb_data, orient='index')
        except Exception:
            pass

    if fb_df is not None and not fb_df.empty:
        # 실시간용 전처리 및 정산 알고리즘 분리
        fb_df['profit'] = pd.to_numeric(fb_df['profit'], errors='coerce').fillna(0)
        fb_df['time'] = pd.to_datetime(fb_df['time'], unit='s')
        fb_df = fb_df.sort_values(by='time').reset_index(drop=True)
        fb_df['cumulative_profit'] = fb_df['profit'].cumsum()
        
        # 실시간 데이터 통계 산출
        rt_total_profit = fb_df['profit'].sum()
        rt_total_trades = len(fb_df)
        rt_win_trades = len(fb_df[fb_df['profit'] > 0])
        rt_win_rate = (rt_win_trades / rt_total_trades * 100) if rt_total_trades > 0 else 0
        
        # 실시간 스탯 표시
        c1, c2, c3 = st.columns(3)
        c1.metric("실시간 누적 총 손익", f"${rt_total_profit:,.2f}")
        c2.metric("총 연동 거래 건수", f"{rt_total_trades}건")
        c3.metric("실시간 승률", f"{rt_win_rate:.1f}%")
        
        # 실시간 전용 자산 성장 곡선 그래프 (Plotly 화려하게 구현)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=fb_df['time'], y=fb_df['cumulative_profit'],
            mode='lines+markers', name='누적 손익($)',
            line=dict(color='#00ffcc', width=2)
        ))
        fig.update_layout(
            title="🎯 실시간 자산 성장 곡선 (Equity Curve)",
            template="plotly_dark", xaxis_title="거래 시간", yaxis_title="누적 수익 ($)"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📋 최근 실시간 체결 내역 (최신 10건)")
        st.dataframe(fb_df.tail(10)[['time', 'symbol', 'type', 'volume', 'price', 'profit']], use_container_width=True)
    else:
        st.info("파이어베이스 창고가 비어있거나 연결을 대기 중입니다. 남편분 PC에서 rt_bridge.py를 실행하세요.")
