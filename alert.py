import time
import requests
import pandas as pd
from collections import defaultdict
from datetime import datetime
import os
import asyncio
from telegram import Bot

# ===== 텔레그램 설정 =====
TELEGRAM_TOKEN = "7475326912:AAHdnqpXNyOiSclg56zFvqu3gTq3CDXexXU"
TELEGRAM_CHAT_ID = 7692872494
bot = Bot(token=TELEGRAM_TOKEN)

# ===== 시스템 설정 =====
INTERVAL = 60
ALERT_COOLDOWN = 300
alerted_at = defaultdict(lambda: 0)
trend_alerted_at = defaultdict(lambda: 0)

# ===== 유틸 =====
def log(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")
    with open("alert_unified.log", "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {msg}\n")

async def send_telegram_alert(msg):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        log(f"Telegram 전송 실패: {e}")

# ===== 데이터 수집 =====
def fetch_candles(symbol, count=6):
    url = f"https://api.upbit.com/v1/candles/minutes/1?market={symbol}&count={count}"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            df = pd.DataFrame(res.json())
            if not df.empty:
                return df.iloc[::-1].reset_index(drop=True)
    except Exception as e:
        log(f"❌ {symbol} 캔들 요청 실패: {e}")
    return pd.DataFrame()

def get_top_symbols():
    try:
        market_res = requests.get("https://api.upbit.com/v1/market/all", timeout=5)
        krw_markets = [m['market'] for m in market_res.json() if m['market'].startswith("KRW-")]
        ticker_url = f"https://api.upbit.com/v1/ticker?markets={','.join(krw_markets)}"
        ticker_res = requests.get(ticker_url, timeout=5)
        sorted_data = sorted(ticker_res.json(), key=lambda x: x['acc_trade_price_24h'], reverse=True)
        return [item['market'] for item in sorted_data[:20]]
    except Exception as e:
        log(f"❌ 종목 리스트 가져오기 실패: {e}")
        return []

# ===== 하이킨 아시 변환 =====
def convert_to_heikin_ashi(df):
    ha_df = pd.DataFrame(index=df.index)
    ha_df['close'] = (df['opening_price'] + df['high_price'] + df['low_price'] + df['trade_price']) / 4

    ha_open = [(df['opening_price'][0] + df['trade_price'][0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i-1] + ha_df['close'][i-1]) / 2)
    ha_df['open'] = ha_open

    ha_df['high'] = df[['high_price', 'opening_price', 'trade_price']].max(axis=1)
    ha_df['low'] = df[['low_price', 'opening_price', 'trade_price']].min(axis=1)

    return ha_df

# ===== 감시 및 분석 =====
async def detect_change(symbol):
    df = fetch_candles(symbol, 6)
    if df.empty or len(df) < 5:
        log(f"⚠️ {symbol}: 데이터 부족")
        return

    now = time.time()
    name = symbol.split('-')[1]
    p0 = df.loc[0, 'trade_price']
    p3 = df.loc[3, 'trade_price']
    change_day = df.loc[0, 'change_rate'] * 100 if 'change_rate' in df.columns else 0

    key_3min = symbol + '_3min'
    key_trend = symbol + '_trend'

    # 1. 3분 변동률 알림
    change_3min = ((p0 - p3) / p3) * 100
    if abs(change_3min) >= 2.0 and now - alerted_at[key_3min] > ALERT_COOLDOWN:
        dir = "상승" if change_3min > 0 else "하락"
        msg = f"📈 {name} {dir} 중 (3분 대비 {change_3min:+.2f}%) (전일대비: {change_day:+.2f}%)"
        log(msg)
        await send_telegram_alert(msg)
        alerted_at[key_3min] = now

    # 2. 하이킨 아시 추세 전환 (보수적 판단)
    ha_df = convert_to_heikin_ashi(df)

    # 과거 2봉이 동일 추세인지
    prev_bearish = all(ha_df.loc[i, 'close'] < ha_df.loc[i, 'open'] for i in [3, 2])
    prev_bullish = all(ha_df.loc[i, 'close'] > ha_df.loc[i, 'open'] for i in [3, 2])

    # 현재 2봉이 반대 추세로 연속인지
    curr_bullish = all(ha_df.loc[i, 'close'] > ha_df.loc[i, 'open'] for i in [1, 0])
    curr_bearish = all(ha_df.loc[i, 'close'] < ha_df.loc[i, 'open'] for i in [1, 0])

    if prev_bearish and curr_bullish and now - trend_alerted_at[key_trend] > ALERT_COOLDOWN:
        msg = f"🚨 {name} 하이킨아시 추세 전환 (음봉 ➔ 양봉 확정)"
        log(msg)
        await send_telegram_alert(msg)
        trend_alerted_at[key_trend] = now

    elif prev_bullish and curr_bearish and now - trend_alerted_at[key_trend] > ALERT_COOLDOWN:
        msg = f"🔄 {name} 하이킨아시 추세 전환 (양봉 ➔ 음봉 확정)"
        log(msg)
        await send_telegram_alert(msg)
        trend_alerted_at[key_trend] = now

# ===== 메인 =====
async def main():
    log("🚀 1분봉 변화 감시 시스템 시작 (하이킨아시: 보수적 기준)")
    await send_telegram_alert("🚀 Azure 서버 1분봉 감시 시스템 시작됨 (하이킨아시 보수적 모드)")

    while True:
        try:
            symbols = get_top_symbols()
            if symbols:
                log(f"🔍 감시 대상: {[s.split('-')[1] for s in symbols]}")
                for symbol in symbols:
                    await detect_change(symbol)
            await asyncio.sleep(INTERVAL)
        except Exception as e:
            log(f"오류 발생: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
