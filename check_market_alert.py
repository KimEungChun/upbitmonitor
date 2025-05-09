import time
import requests
from datetime import datetime
import asyncio
from telegram import Bot

# ===== 텔레그램 설정 =====
TELEGRAM_TOKEN = "7475326912:AAHdnqpXNyOiSclg56zFvqu3gTq3CDXexXU"
TELEGRAM_CHAT_ID = 7692872494
bot = Bot(token=TELEGRAM_TOKEN)

# ===== 시스템 설정 =====
LOG_FILE = "price_log.txt"
HEALTHCHECK_INTERVAL = 3600
INTERVAL = 300  # 5분 간격
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
        url = f"https://api.upbit.com/v1/candles/minutes/5?market={symbol}&count=100"
        return requests.get(url).json()
    except Exception as e:
        log(f"❌ OHLCV 가져오기 실패 ({symbol}): {e}")
        return []

# ===== 하이킨 아시 변환 =====
def convert_to_heikin_ashi(ohlcv_data):
    ha_data = []
    for i, candle in enumerate(reversed(ohlcv_data)):
        close = candle['trade_price']
        open_ = candle['opening_price']
        high = candle['high_price']
        low = candle['low_price']

        ha_close = (open_ + high + low + close) / 4

        if i == 0:
            ha_open = (open_ + close) / 2
        else:
            prev = ha_data[-1]
            ha_open = (prev['open'] + prev['close']) / 2

        ha_high = max(high, ha_open, ha_close)
        ha_low = min(low, ha_open, ha_close)

        ha_data.append({
            'open': ha_open,
            'close': ha_close,
            'high': ha_high,
            'low': ha_low,
        })

    return list(reversed(ha_data))

# ===== 하이킨 아시 기반 추세 판단 =====
def detect_heikin_ashi_trend(ha_data):
    recent = ha_data[-20:]  # 최근 20개 캔들 기준
    up_count = sum(1 for c in recent if c['close'] > c['open'])
    down_count = sum(1 for c in recent if c['close'] < c['open'])

    if up_count >= 14:
        return "상승중"
    elif down_count >= 14:
        return "하락중"
    else:
        return "보합중"

# ===== 메인 모니터링 루프 =====
async def monitor():
    log("🚀 하이킨 아시 추세 모니터링 시작")
    await send_telegram_alert("🚀 하이킨 아시 추세 모니터링 시스템 시작됨")

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
                if len(ohlcv_data) < 20:
                    continue

                ha_data = convert_to_heikin_ashi(ohlcv_data)
                trend = detect_heikin_ashi_trend(ha_data)
                coin_name = symbol.split('-')[1]

                # 변동률 계산 및 이모지 적용
                ticker = ticker_info.get(symbol)
                if not ticker:
                    continue
                try:
                    current_price = ticker['trade_price']
                    prev_close = ticker['prev_closing_price']
                    change_rate = ((current_price - prev_close) / prev_close) * 100
                    emoji = "🔸" if change_rate >= 0 else "🔹"
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

            msg = "\n".join([
                "📈 하이킨 아시 추세 분석:",
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

# ===== 실행 =====
if __name__ == "__main__":
    asyncio.run(monitor())