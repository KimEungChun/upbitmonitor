import time
import requests
import csv
import math
from datetime import datetime
from market_data_pool import MarketDataPool
from telegram import Bot
import asyncio

# ===== 텔레그램 설정 =====
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"
bot = Bot(token=TELEGRAM_TOKEN)

# ===== 시스템 설정 =====
INTERVAL = 0.25
CANDLE_COUNT = 60
CORRELATION_THRESHOLD = 0.85
CSV_FILENAME = "ha_correlation_pairs.csv"

# ===== 로깅 =====
def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open("correlation_analysis.log", "a", encoding="utf-8") as f:
        f.write(full_message + "\n")

async def send_telegram_alert(msg):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        log(f"Telegram 전송 실패: {e}")

# ===== 캔들 데이터 수집 =====
def fetch_closes(symbol, count=CANDLE_COUNT):
    url = f"https://api.upbit.com/v1/candles/minutes/5?market={symbol}&count={count}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            closes = [item['trade_price'] for item in reversed(data)]
            return closes
    except Exception as e:
        log(f"❌ {symbol} 데이터 수집 실패: {e}")
    return []

# ===== 수익률 계산 =====
def calc_returns(prices):
    return [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]

# ===== 상관계수 계산 =====
def pearson_corr(x, y):
    if len(x) != len(y):
        return 0
    n = len(x)
    avg_x = sum(x) / n
    avg_y = sum(y) / n
    num = sum((x[i] - avg_x) * (y[i] - avg_y) for i in range(n))
    den_x = math.sqrt(sum((x[i] - avg_x) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((y[i] - avg_y) ** 2 for i in range(n)))
    if den_x == 0 or den_y == 0:
        return 0
    return num / (den_x * den_y)

# ===== 상관관계 분석 및 저장 =====
def build_correlation_csv(symbols, filename=CSV_FILENAME):
    prices_map = {}
    for symbol in symbols:
        closes = fetch_closes(symbol)
        if len(closes) == CANDLE_COUNT:
            prices_map[symbol] = calc_returns(closes)
        time.sleep(INTERVAL)

    pairs = []
    keys = list(prices_map.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            s1, s2 = keys[i], keys[j]
            corr = pearson_corr(prices_map[s1], prices_map[s2])
            if corr >= CORRELATION_THRESHOLD:
                pairs.append([s1, s2, round(corr, 3)])

    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Symbol A", "Symbol B", "Correlation"])
        writer.writerows(pairs)
    log(f"✅ CSV 저장 완료: {filename}")
    return pairs

# ===== 메인 분석 루프 =====
async def main():
    log("🚀 상관관계 분석 시작")
    await send_telegram_alert("🚀 상관관계 분석 시스템 시작됨")
    pool = MarketDataPool(mode='A')
    watchlist = pool.get_top_symbols()
    log(f"🔍 감시 종목 수: {len(watchlist)}")
    result = build_correlation_csv(watchlist)
    await send_telegram_alert(f"🎯 분석 완료 - 커플링 {len(result)}건 발견됨")

if __name__ == "__main__":
    asyncio.run(main())