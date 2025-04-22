import time
import requests
from datetime import datetime
from collections import defaultdict, deque

# 설정
THRESHOLDS_DEFAULT = {1: 1.0, 3: 3.0}
THRESHOLDS_SPECIAL = {1: 0.33, 3: 0.66}
SPECIAL_SYMBOLS = {"KRW-BTC", "KRW-XRP"}

LOG_FILE = "price_log.txt"
HEALTHCHECK_INTERVAL = 3600
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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"

# 데이터 저장
price_history = defaultdict(lambda: deque(maxlen=6))
prev_day_price = {}
alerted_at = defaultdict(lambda: 0)
last_healthcheck = 0

def get_top_krw_markets(limit=20):
    market_url = "https://api.upbit.com/v1/market/all"
    market_data = requests.get(market_url).json()
    krw_markets = [m['market'] for m in market_data if m['market'].startswith("KRW-")]

    ticker_url = f"https://api.upbit.com/v1/ticker?markets={','.join(krw_markets)}"
    ticker_data = requests.get(ticker_url).json()

    sorted_data = sorted(ticker_data, key=lambda x: x['acc_trade_price_24h'], reverse=True)
    return sorted_data[:limit]

def log(message):
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")

def send_alert(symbol, change_percent, percent_from_prev_day, direction, minutes_ago):
    now = int(time.time())
    alert_key = f"{symbol}_{minutes_ago}m"
    if now - alerted_at[alert_key] < 60:
        return
    alerted_at[alert_key] = now

    change_str = f"{change_percent:+.2f}%"
    prev_day_str = f"{percent_from_prev_day:+.2f}%"
    message = f"[{symbol}] {minutes_ago}분 전보다 {direction}: {change_str} (전일대비: {prev_day_str})"
    log(f"🚨 ALERT ({minutes_ago}분): {message}")

    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message})
    except Exception as e:
        log(f"Slack 전송 실패: {e}")

def send_healthcheck():
    global last_healthcheck
    now = int(time.time())
    if now - last_healthcheck >= HEALTHCHECK_INTERVAL:
        message = f"✅ [헬스체크] 모니터링 정상 작동 중 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        log(message)
        try:
            requests.post(SLACK_WEBHOOK_URL, json={"text": message})
        except Exception as e:
            log(f"Slack 헬스체크 전송 실패: {e}")
        last_healthcheck = now

def monitor():
    while True:
        send_healthcheck()
        all_top_data = get_top_krw_markets(20)
        alert_top_data = all_top_data[:10]  # alert은 상위 10개만

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

            for minutes_ago in [1, 3]:  # 5분 alert 제거됨
                if len(price_history[symbol]) >= minutes_ago + 1:
                    old_price = price_history[symbol][-1 - minutes_ago]
                    change_percent = ((current_price - old_price) / old_price) * 100
                    direction = "상승" if change_percent > 0 else "하락"

                    if abs(change_percent) >= thresholds[minutes_ago]:
                        send_alert(symbol.split("-")[1], change_percent, percent_from_prev_day, direction, minutes_ago)

        time.sleep(60)

if __name__ == "__main__":
    monitor()
