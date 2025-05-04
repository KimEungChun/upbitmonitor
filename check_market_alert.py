# check_market_telegram.py (가격 급등/급락 알림 → 텔레그램 발송)

import time
import requests
from datetime import datetime
from collections import defaultdict, deque
import asyncio
from telegram import Bot

# ===== 텔레그램 설정 =====
TELEGRAM_TOKEN = "여기에_봇_토큰_입력"
TELEGRAM_CHAT_ID = 123456789  # 숫자로

bot = Bot(token=TELEGRAM_TOKEN)

# ===== 설정 =====
THRESHOLDS_DEFAULT = {1: 1.0, 3: 3.0}
THRESHOLDS_SPECIAL = {1: 0.33, 3: 0.66}
SPECIAL_SYMBOLS = {"KRW-BTC", "KRW-XRP"}

LOG_FILE = "price_log.txt"
HEALTHCHECK_INTERVAL = 3600

# ===== 상태 저장 =====
price_history = defaultdict(lambda: deque(maxlen=6))
prev_day_price = {}
alerted_at = defaultdict(lambda: 0)
last_healthcheck = 0

# ===== 유틸 =====
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

def get_top_krw_markets(limit=20):
    try:
        market_url = "https://api.upbit.com/v1/market/all"
        market_data = requests.get(market_url, timeout=5).json()
        krw_markets = [m['market'] for m in market_data if m['market'].startswith("KRW-")]

        ticker_url = f"https://api.upbit.com/v1/ticker?markets={','.join(krw_markets)}"
        ticker_data = requests.get(ticker_url, timeout=5).json()

        sorted_data = sorted(ticker_data, key=lambda x: x['acc_trade_price_24h'], reverse=True)
        return sorted_data[:limit]
    except Exception as e:
        log(f"❌ 상위 종목 조회 실패: {e}")
        return []

def send_healthcheck():
    global last_healthcheck
    now = int(time.time())
    if now - last_healthcheck >= HEALTHCHECK_INTERVAL:
        msg = f"✅ 헬스체크: 시스템 정상 작동 중 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        log(msg)
        asyncio.run(send_telegram_alert(msg))
        last_healthcheck = now

def send_alert(symbol, change_percent, percent_from_prev_day, direction, minutes_ago):
    now = int(time.time())
    alert_key = f"{symbol}_{minutes_ago}m"
    if now - alerted_at[alert_key] < 60:
        return
    alerted_at[alert_key] = now

    name = symbol.split('-')[1]
    msg = (
        f"🚨 {name} {minutes_ago}분 전 대비 {direction}\n"
        f"등락률: {change_percent:+.2f}% | 전일대비: {percent_from_prev_day:+.2f}%"
    )
    log(msg)
    asyncio.run(send_telegram_alert(msg))

# ===== 모니터링 루프 =====
def monitor():
    log("🚀 가격 모니터링 시스템 시작 (텔레그램 알림 모드)")
    asyncio.run(send_telegram_alert("🚀 가격 급등락 감시 봇 시작됨 (텔레그램 알림)"))

    while True:
        send_healthcheck()

        all_top_data = get_top_krw_markets(20)
        alert_targets = all_top_data[:10]

        for coin in alert_targets:
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
                        send_alert(symbol, change_percent, percent_from_prev_day, direction, minutes_ago)

        time.sleep(60)

# ===== 실행 =====
if __name__ == "__main__":
    monitor()
