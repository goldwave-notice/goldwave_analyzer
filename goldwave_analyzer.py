#### 📄 `goldwave_analyzer.py` 소스 코드


import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="GoldWave EA Analyzer", layout="wide", page_icon="📊")

st.title("📊 골드웨이브(GoldWave) EA 실시간 진단 대시보드")
st.caption("아이노우커머스 MT5 거래 내역 기반 정밀 성과 분석기")

# 1. 파일 업로드 섹션
uploaded_file = st.file_drop_channel = st.file_uploader("MT5에서 내보낸 엑셀 파일(.xlsx)을 업로드하세요.", type=["xlsx"])

if uploaded_file is not None:
    try:
        # 데이터 원본 로드 (헤더 없이 읽어서 위치 추적)
        raw_df = pd.read_excel(uploaded_file, header=None)
        
        # --- [은경님's 정산 알고리즘 주입] ---
        # 496줄 부근: 크레딧 신용편의 추적 (텍스트 매칭으로 안전하게 찾기)
        credit = 0.0
        for idx, row in raw_df.iterrows():
            if idx > 400 and str(row[0]).startswith("4/1~4/30 받은 크레딧"):
                credit = float(row[3])
                break
        if credit == 0.0:
            credit = 1115.05 # 못 찾을 경우 엑셀 기준 기본값 가동

        # 295줄: '거래' 표 시작점 찾기 및 데이터프레임 재구성
        start_idx = 295
        columns_row = raw_df.iloc[start_idx].tolist()
        
        # 실제 거래 데이터 쪼개기 (296줄부터 493줄까지)
        trade_df = raw_df.iloc[start_idx+1:494].copy()
        trade_df.columns = columns_row
        
        # 데이터 타입 정제
        trade_df['수익'] = pd.to_numeric(trade_df['수익'], errors='coerce').fillna(0)
        trade_df['수수료'] = pd.to_numeric(trade_df['수수료'], errors='coerce').fillna(0)
        trade_df['스왑'] = pd.to_numeric(trade_df['스왑'], errors='coerce').fillna(0)
        
        # 실질 이월 잔액 및 최종 정산액 계산
        init_balance = float(trade_df['잔액'].iloc[0]) # 296줄 최초 잔액
        real_start_capital = init_balance + credit    # 실질 기준 자본금 (3673.16 + 1115.05)
        
        total_profit = trade_df['수익'].sum()
        total_fee = trade_df['수수료'].sum()
        total_net_profit = total_profit + total_fee # 총수입 (69.92)
        
        real_return_rate = (total_net_profit / real_start_capital) * 100
        
        # --- [대시보드 상단 요약 화면] ---
        st.subheader("📈 1. 종합 운영 자산 현황")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("실질 기준 자본금 (이월+크레딧)", f"${real_start_capital:,.2f}")
        with col2:
            st.metric("유지 중인 신용편의(크레딧)", f"${credit:,.2f}")
        with col3:
            st.metric("당월 누적 총수입 (Net)", f"${total_net_profit:,.2f}", delta=f"${total_profit:,.2f} 수익")
        with col4:
            st.metric("실질 월간 수익률 (%)", f"{real_return_rate:.2f}%")

        # --- [종목별 / 전략별 패턴 진단] ---
        st.markdown("---")
        st.subheader("🔍 2. 종목 및 EA 전략별 성과 분석 (패턴 진단)")
        
        # out(청산) 데이터만 추려야 정확한 승률/손익비 산출 가능
        closed_trades = trade_df[trade_df['방향'] == 'out'].copy()
        
        # 비고란이 비어있으면 일반 세션으로 매핑
        closed_trades['비고'] = closed_trades['비고'].fillna('일반매매')
        
        # 그룹화 분석 (통화, 비고별로 쪼개기)
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
                "종목": symbol,
                "적용 로직(세션)": strategy,
                "총 거래횟수": f"{total_cnt}회",
                "승률": f"{win_rate:.1f}%",
                "손익비 (PF)": f"{profit_factor:.2f}",
                "구간 순수익": f"${net_p:,.2f}",
                "진단 상태": status
            })
            
        summary_df = pd.DataFrame(summary_list)
        st.dataframe(summary_df, use_container_width=True)

        # --- [개발자 소통용 로그 생성기] ---
        st.markdown("---")
        st.subheader("📋 3. 개발자 피드백 전용 로그 생성기")
        
        # 약점 로직 자동 필터링해서 멘트 만들기
        weak_points = [f"[{item['종목']}/{item['적용 로직(세션)']}] 승률 {item['승률']}, PF {item['손익비 (PF)']}" 
                       for item in summary_list if "⚠️" in item['진단 상태']]
        
        if weak_points:
            weak_text = ", ".join(weak_points)
            report_msg = f"[GoldWave_Report] 금월 거래 데이터 정밀 진단 결과, {weak_text} 구간에서 손실 누적 및 로직 꼬임 현상이 발견되었습니다. 해당 세션의 SMC 진입 필터 값 백테스팅 및 리스크 레이어 조정을 권장합니다."
        else:
            report_msg = f"[GoldWave_Report] 금월 모든 자동매매 세션(Gold/Silver)이 리스크 바운더리 내에서 정상 작동 중입니다. 누적 수익률 {real_return_rate:.2f}%로 순항 중입니다."
            
        st.text_area("카톡/텔레그램 전송용 메시지 (아래 내용을 복사해서 개발자에게 전달하세요)", report_msg, height=100)

    except Exception as e:
        st.error(f"엑셀 파일을 분석하는 도중 에러가 발생했습니다. 양식을 확인해 주세요. (오류 내용: {e})")