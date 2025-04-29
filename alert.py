import time
import requests
import pandas as pd
from collections import defaultdict, deque
from datetime import datetime
import os

# 환경 변수 로드
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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"

# ===== 설정 =====
INTERVAL = 60
ALERT_COOLDOWN = 300  # 5분 쿨다운

# ===== 상태 저장 =====
alerted_at = defaultdict(lambda: 0)

# ===== 유틸 =====
def log(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")
    with open("alert_unified.log", "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {msg}\n")

def send_slack_alert(msg):
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": msg})
    except Exception as e:
        log(f"Slack 전송 실패: {e}")

# ===== 데이터 수집 =====
def fetch_candles(symbol, count=6):
    url = f"https://api.upbit.com/v1/candles/minutes/1?market={symbol}&count={count}"
    for i in range(2):
        try:
            res = requests.get(url)
            if res.status_code == 200:
                df = pd.DataFrame(res.json())
                if not df.empty:
                    return df.iloc[::-1].reset_index(drop=True)
        except Exception as e:
            log(f"❌ {symbol} 칸들 요청 실패 ({i+1}회): {e}")
        time.sleep(0.3)
    return pd.DataFrame()

# ===== 분석 및 감지 =====
def detect_change(symbol):
    df = fetch_candles(symbol, 6)
    if df.empty or len(df) < 6:
        log(f"⚠️ {symbol}: 데이터 부족")
        return

    name = symbol.split('-')[1]
    now = time.time()

    # 현재가, 2분 전, 5분 전 가격
    p0 = df.loc[0, 'trade_price']
    p2 = df.loc[2, 'trade_price']
    p5 = df.loc[5, 'trade_price']
    change_2 = ((p0 - p2) / p2) * 100
    change_5 = ((p0 - p5) / p5) * 100
    change_day = df.loc[0, 'change_rate'] * 100 if 'change_rate' in df.columns else 0

    key_2 = symbol + '_2min'
    key_5 = symbol + '_5min'

    # 5분 먼저 체크
    if abs(change_5) >= 2.0:
        if now - alerted_at[key_5] > ALERT_COOLDOWN:
            dir = "상승" if change_5 > 0 else "하락"
            msg = f"📊 {name} {dir} 중 (5분대비: {change_5:+.2f}%) (금일: {change_day:+.1f}%)"
            log(msg)
            send_slack_alert(msg)
            alerted_at[key_5] = now
            alerted_at[key_2] = now  # 2분 중복 방지용 조기 설정

    elif abs(change_2) >= 1.5:
        if now - alerted_at[key_2] > ALERT_COOLDOWN:
            dir = "상승" if change_2 > 0 else "하락"
            msg = f"📊 {name} {dir} 중 (2분대비: {change_2:+.2f}%) (금일: {change_day:+.1f}%)"
            log(msg)
            send_slack_alert(msg)
            alerted_at[key_2] = now

# ===== 종목 선정 =====
def get_top_symbols():
    url = "https://api.upbit.com/v1/market/all"
    markets = requests.get(url).json()
    krw_markets = [m['market'] for m in markets if m['market'].startswith("KRW-")]

    ticker_url = f"https://api.upbit.com/v1/ticker?markets={','.join(krw_markets)}"
    tickers = requests.get(ticker_url).json()
    sorted_data = sorted(tickers, key=lambda x: x['acc_trade_price_24h'], reverse=True)
    return [item['market'] for item in sorted_data[:20]]

# ===== 메인 루프 =====
def main():
    log("🚀 1분봉 변화 그래 감시 시스템 시작")
    while True:
        try:
            symbols = get_top_symbols()
            log(f"🔍 감시 대상: {[s.split('-')[1] for s in symbols]}")
            
            for symbol in symbols:
                detect_change(symbol)
            time.sleep(INTERVAL)
        except Exception as e:
            log(f"오류 발생: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
