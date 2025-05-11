import time
import requests
from datetime import datetime
import asyncio
from telegram import Bot

# ===== 텔레그램 설정 =====
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = YOUR_TELEGRAM_CHAT_ID  # 숫자

bot = Bot(token=TELEGRAM_TOKEN)

# ===== 시스템 설정 =====
LOG_FILE = "price_log.txt"
HEALTHCHECK_INTERVAL = 3600
INTERVAL = 300
last_healthcheck = 0

# ===== 유틸 함수 =====
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

# ===== 업비트 API =====
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

def get_ohlcv(symbol):
    try:
        url = f"https://api.upbit.com/v1/candles/minutes/5?market={symbol}&count=30"
        return requests.get(url).json()
    except Exception as e:
        log(f"❌ OHLCV 가져오기 실패 ({symbol}): {e}")
        return []

def get_daily_ohlcv(symbol):
    try:
        url = f"https://api.upbit.com/v1/candles/days?market={symbol}&count=2"
        response = requests.get(url)
        data = response.json()
        if len(data) >= 2:
            return data[1]
        else:
            return None
    except Exception as e:
        log(f"❌ 일봉 데이터 가져오기 실패 ({symbol}): {e}")
        return None

def get_yesterday_avg_change(symbols):
    total_change = 0
    count = 0

    for symbol in symbols:
        daily = get_daily_ohlcv(symbol)
        if not daily:
            continue
        try:
            open_price = daily['opening_price']
            close_price = daily['trade_price']
            change = ((close_price - open_price) / open_price) * 100
            total_change += change
            count += 1
        except:
            continue

    if count == 0:
        return None
    return total_change / count

# ===== 수정된 추세 판단 함수 (하이킨 아시 제거, 캔들 기준 분석) =====
def detect_custom_trend(candles):
    if len(candles) < 30:
        return "보합중"

    candles = list(reversed(candles))  # 시간 순 정렬
    base_high = candles[0]['high_price']
    base_low = candles[0]['low_price']
    high_break = False
    low_break = False
    up_count = 0
    down_count = 0

    for c in candles[1:]:
        if c['high_price'] > base_high:
            high_break = True
        if c['low_price'] < base_low:
            low_break = True

        if c['trade_price'] > c['opening_price']:
            up_count += 1
        elif c['trade_price'] < c['opening_price']:
            down_count += 1

    if high_break and up_count >= 15:
        return "상승중"
    elif low_break and down_count >= 15:
        return "하락중"
    else:
        return "보합중"

# ===== 메인 루프 =====
async def monitor():
    log("🚀 캔들 기반 추세 모니터링 시작")
    await send_telegram_alert("🚀 캔들 기반 추세 모니터링 시스템 시작 됨")

    while True:
        try:
            await send_healthcheck()
            top_data = get_top_krw_markets()
            symbols = [c['market'] for c in top_data]
            ticker_info = {item['market']: item for item in top_data}

            trends_up = []
            trends_down = []
            trends_flat = []

            for symbol in symbols:
                ohlcv_data = get_ohlcv(symbol)
                if len(ohlcv_data) < 30:
                    continue

                trend = detect_custom_trend(ohlcv_data)
                coin_name = symbol.split('-')[1]
                ticker = ticker_info.get(symbol)
                if not ticker:
                    continue
                try:
                    current_price = ticker['trade_price']
                    prev_close = ticker['prev_closing_price']
                    change_rate = ((current_price - prev_close) / prev_close) * 100
                    emoji = "🔹" if change_rate >= 0 else "🔸"
                    change_rate_str = f"{emoji} {change_rate:+.1f}%"
                except Exception as e:
                    change_rate_str = "N/A"

                coin_display = f"{coin_name}({change_rate_str})"

                if trend == "상승중":
                    trends_up.append(coin_display)
                elif trend == "하락중":
                    trends_down.append(coin_display)
                else:
                    trends_flat.append(coin_display)

            # 평균 수익률 계산 (금일)
            total_change = 0
            count = 0
            for item in top_data:
                try:
                    current = item['trade_price']
                    prev = item['prev_closing_price']
                    change = ((current - prev) / prev) * 100
                    total_change += change
                    count += 1
                except:
                    continue

            avg_change = total_change / count if count > 0 else 0
            avg_emoji = "🔸" if avg_change >= 0 else "🔹"
            avg_str = f"{avg_emoji} {avg_change:+.2f}%"

            # 어제 평균 수익률
            yesterday_avg = get_yesterday_avg_change(symbols)
            if yesterday_avg is not None:
                y_avg_emoji = "🔸" if yesterday_avg >= 0 else "🔹"
                y_avg_str = f"{y_avg_emoji} {yesterday_avg:+.2f}%"
            else:
                y_avg_str = "N/A"

            msg = "\n".join([
                "📈 추세 분석:",
                f"📊 오늘 시장 평균 수익률 (09:00 기준): {avg_str}",
                f"📉 어제 시장 평균 수익률 (전일 09:00 ~ 금일 08:59): {y_avg_str}",
                f"상승중 {len(trends_up)}개: {', '.join(trends_up) or '없음'}",
                f"보합중 {len(trends_flat)}개: {', '.join(trends_flat) or '없음'}",
                f"하락중 {len(trends_down)}개: {', '.join(trends_down) or '없음'}"
            ])

            log(msg)
            await send_telegram_alert(msg)
            await asyncio.sleep(INTERVAL)

        except Exception as e:
            log(f"❌ 오류 발생: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(monitor())
