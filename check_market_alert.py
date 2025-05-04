# check_market_alert.py (가격 모니터링 + 텔레그램 알림)

import time
import requests
from datetime import datetime
from collections import defaultdict, deque
import asyncio
from telegram import Bot

# ===== 텔레그램 설정 =====
TELEGRAM_TOKEN = "7475326912:AAHdnqpXNyOiSclg56zFvqu3gTq3CDXexXU"
TELEGRAM_CHAT_ID = 7692872494
bot = Bot(token=TELEGRAM_TOKEN)

# ===== 시스템 설정 =====
THRESHOLDS_DEFAULT = {1: 1.0, 3: 3.0}
THRESHOLDS_SPECIAL = {1: 0.33, 3: 0.66}
SPECIAL_SYMBOLS = {"KRW-BTC", "KRW-XRP"}
LOG_FILE = "price_log.txt"
HEALTHCHECK_INTERVAL = 3600
INTERVAL = 60

# 상태 저장
price_history = defaultdict(lambda: deque(maxlen=6))
prev_day_price = {}
alerted_at = defaultdict(lambda: 0)
last_healthcheck = 0

# 유틸 함수

def log(message):
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")

async def send_telegram_alert(msg):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        log(f"Telegram 전송 실패: {e}")

async def send_healthcheck():
    global last_healthcheck
    now = int(time.time())
    if now - last_healthcheck >= HEALTHCHECK_INTERVAL:
        message = f"✅ [헬스] 시스템 정상 작동 중 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        log(message)
        await send_telegram_alert(message)
        last_healthcheck = now

# 시장 정보 조회

def get_top_krw_markets(limit=20):
    try:
        market_data = requests.get("https://api.upbit.com/v1/market/all").json()
        krw_markets = [m['market'] for m in market_data if m['market'].startswith("KRW-")]

        ticker_url = f"https://api.upbit.com/v1/ticker?markets={','.join(krw_markets)}"
        ticker_data = requests.get(ticker_url).json()

        sorted_data = sorted(ticker_data, key=lambda x: x['acc_trade_price_24h'], reverse=True)
        return sorted_data[:limit]
    except Exception as e:
        log(f"❌ 종목 리스트 가져오기 실패: {e}")
        return []

async def monitor():
    log("🚀 가격 모니터링 시스템 시작 (텔레그램 알림 모드)")
    await send_telegram_alert("🚀 가격 모니터링 시스템 시작됨 (텔레그램 알림 모드)")

    while True:
        try:
            await send_healthcheck()
            all_top_data = get_top_krw_markets(20)
            alert_top_data = all_top_data[:10]  # 상위 10개만 감시

            for coin in alert_top_data:
                symbol = coin['market']
                current_price = coin['trade_price']
                yesterday_price = coin.get('prev_closing_price')

                if not yesterday_price:
                    continue

                prev_day_price[symbol] = yesterday_price
                percent_from_prev_day = ((current_price - yesterday_price) / yesterday_price) * 100
                price_history[symbol].append(current_price)

                thresholds = THRESHOLDS_SPECIAL if symbol in SPECIAL_SYMBOLS else THRESHOLDS_DEFAULT

                for minutes_ago in [1, 3]:
                    if len(price_history[symbol]) >= minutes_ago + 1:
                        old_price = price_history[symbol][-1 - minutes_ago]
                        change_percent = ((current_price - old_price) / old_price) * 100
                        direction = "상승" if change_percent > 0 else "하락"

                        if abs(change_percent) >= thresholds[minutes_ago]:
                            key = f"{symbol}_{minutes_ago}m"
                            now = int(time.time())
                            if now - alerted_at[key] >= 60:
                                alerted_at[key] = now
                                msg = f"[{symbol.split('-')[1]}] {minutes_ago}분 전보다 {direction}: {change_percent:+.2f}% (전일: {percent_from_prev_day:+.2f}%)"
                                log(f"🚨 ALERT: {msg}")
                                await send_telegram_alert(f"🚨 {msg}")

            await asyncio.sleep(INTERVAL)

        except Exception as e:
            log(f"오류 발생: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(monitor())
