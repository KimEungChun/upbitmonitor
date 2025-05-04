# check_market_alert.py (시장 현황 분석 → 텔레그램 알림)

import time
import requests
import pandas as pd
from datetime import datetime
import os
import asyncio
from telegram import Bot
import pyupbit

# ===== 텔레그램 설정 =====
TELEGRAM_TOKEN = "7475326912:AAHdnqpXNyOiSclg56zFvqu3gTq3CDXexXU"
TELEGRAM_CHAT_ID = 7692872494
bot = Bot(token=TELEGRAM_TOKEN)

# ===== 시스템 설정 =====
INTERVAL = 300  # 5분마다

# ===== 유틸 =====
def log(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")
    with open("market_alert.log", "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {msg}\n")

async def send_telegram_alert(msg):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        log(f"Telegram 전송 실패: {e}")

# ===== 캔들/시장 분석 =====
def fetch_candles(symbol, count=100):
    try:
        df = pyupbit.get_ohlcv(symbol, interval="minute5", count=count)
        return df if df is not None and len(df) >= count else pd.DataFrame()
    except:
        return pd.DataFrame()

def heikin_ashi(df):
    ha_df = pd.DataFrame(index=df.index)
    ha_df['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = [(df['open'].iloc[0] + df['close'].iloc[0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i-1] + ha_df['HA_Close'].iloc[i-1]) / 2)
    ha_df['HA_Open'] = ha_open
    return ha_df

def detect_trend(df):
    ma20 = df['close'].rolling(20).mean()
    slope = ma20.diff().mean()
    falling_rate = (df['close'].diff() < 0).sum() / len(df)
    if slope < -0.05 and falling_rate > 0.6:
        return "하락"
    elif slope > 0.05 and falling_rate < 0.4:
        return "상승"
    else:
        return "보합"

def analyze_market():
    url = "https://api.upbit.com/v1/market/all"
    markets = requests.get(url).json()
    krw_symbols = [m['market'] for m in markets if m['market'].startswith("KRW-")]

    ticker_url = f"https://api.upbit.com/v1/ticker?markets={','.join(krw_symbols)}"
    ticker_data = requests.get(ticker_url).json()
    top20 = sorted(ticker_data, key=lambda x: x['acc_trade_price_24h'], reverse=True)[:20]
    top_symbols = [t['market'] for t in top20]

    falling = []
    other = []
    trend_map = {"상승": [], "하락": [], "보합": []}

    for symbol in top_symbols:
        df = fetch_candles(symbol)
        if df.empty:
            continue
        ha = heikin_ashi(df)
        if len(ha) < 3:
            continue
        if ha['HA_Close'].iloc[-3] < ha['HA_Open'].iloc[-3] and ha['HA_Close'].iloc[-2] < ha['HA_Open'].iloc[-2]:
            falling.append(symbol)
        else:
            other.append(symbol)
        trend_map[detect_trend(df)].append(symbol)

    status = "✅ 매수 가능 상태" if len(falling) < 10 else "🚫 매수 중단 상태"
    summary = f"\n📈 시장 현황 분석 (5분봉 기준)\n"
    summary += f"현재 상태: {status} - 연속 음봉 종목 수: {len(falling)}\n\n"
    summary += f"유의 종목 (연속 2봉 음봉): {', '.join([s.split('-')[1] for s in falling])}\n"
    summary += f"기타 종목: {', '.join([s.split('-')[1] for s in other])}\n\n"
    summary += f"📉 추세 분석 결과 (5분봉 100봉)\n"
    for k in ["상승", "하락", "보합"]:
        summary += f"{k} 추세 ({len(trend_map[k])}): {', '.join([s.split('-')[1] for s in trend_map[k]])}\n"
    return summary

# ===== 메인 루프 =====
async def main():
    log("🚀 시장 현황 텔레그램 전송 시스템 시작")
    await send_telegram_alert("🚀 Azure 시장 현황 알림 시스템 시작됨 (5분 간격)")
    while True:
        try:
            report = analyze_market()
            log("시장 현황 분석 완료 → 텔레그램 전송")
            await send_telegram_alert(report)
            await asyncio.sleep(INTERVAL)
        except Exception as e:
            log(f"오류 발생: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
