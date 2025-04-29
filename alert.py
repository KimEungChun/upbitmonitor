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
ALERT_COOLDOWN = 300  # 5분 쿨다운

# 상태
alerted_at = defaultdict(lambda: 0)

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

# ===== 데이터 =====
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

# ===== 감시 및 분석 =====
async def detect_change(symbol):
    df = fetch_candles(symbol, 6)
    if df.empty or len(df) < 6:
        log(f"⚠️ {symbol}: 데이터 부족")
        return

    now = time.time()
    name = symbol.split('-')[1]
    p0 = df.loc[0, 'trade_price']
    p2 = df.loc[2, 'trade_price']
    p5 = df.loc[5, 'trade_price']

    change_2 = ((p0 - p2) / p2) * 100
    change_5 = ((p0 - p5) / p5) * 100
    change_day = df.loc[0, 'change_rate'] * 100 if 'change_rate' in df.columns else 0

    key_2 = symbol + '_2min'
    key_5 = symbol + '_5min'

    # 5분 변동 먼저 체크
    if abs(change_5) >= 2.0 and now - alerted_at[key_5] > ALERT_COOLDOWN:
        dir = "상승" if change_5 > 0 else "하락"
        msg = f"📈 {name} {dir} 중 (5분 대비 {change_5:+.2f}%) (금일 {change_day:+.1f}%)"
        log(msg)
        await send_telegram_alert(msg)
        alerted_at[key_5] = now
        alerted_at[key_2] = now  # 2분 중복 방지

    # 2분 변동 체크
    elif abs(change_2) >= 1.5 and now - alerted_at[key_2] > ALERT_COOLDOWN:
        dir = "상승" if change_2 > 0 else "하락"
        msg = f"📈 {name} {dir} 중 (2분 대비 {change_2:+.2f}%) (금일 {change_day:+.1f}%)"
        log(msg)
        await send_telegram_alert(msg)
        alerted_at[key_2] = now

# ===== 메인 =====
async def main():
    log("🚀 1분봉 변화 감시 시스템 시작")
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
