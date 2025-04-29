import pyupbit
import time
import datetime
import os
import csv
import requests
from dotenv import load_dotenv
from collections import defaultdict
from market_data_pool import MarketDataPool

# 환경 설정
load_dotenv()
access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

upbit = pyupbit.Upbit(access_key, secret_key)

# 전략 파라미터
TRADE_AMOUNT = 200000
MAX_TRADES_PER_DAY = 10
TRADE_INTERVAL = 600
POSITION_MAX_KRW = 1000000

# 상태 저장
last_trade_time = {}
trade_count = defaultdict(int)
current_day = datetime.date.today()

# 데이터 풀 준비
data_pool = MarketDataPool()

# === 유틸 함수 ===
def safe_get_current_price(market):
    data_pool.update()
    price = data_pool.get_price(market)
    if price is None:
        print(f"[가격 조회 실패:{market}] 응답 없음")
        return 0
    return price

def log_to_csv(data):
    with open("rebound_tr_log.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(data)

def send_slack_alert(message):
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json={"text": message})
        if response.status_code != 200:
            print(f"Slack 전송 실패: {response.status_code}, 응답: {response.text}")
    except Exception as e:
        print("Slack 오류:", e)

def get_top_20_symbols():
    data_pool.update()
    return data_pool.get_top_symbols()[:20]

def check_can_trade(market):
    global current_day
    now = time.time()
    today = datetime.date.today()
    if today != current_day:
        trade_count.clear()
        current_day = today
    if trade_count[market] >= MAX_TRADES_PER_DAY:
        return False
    if market in last_trade_time and now - last_trade_time[market] < TRADE_INTERVAL:
        return False
    return True

def fetch_recent_prices(market):
    df = pyupbit.get_ohlcv(market, interval="minute5", count=50)
    return df if df is not None and len(df) >= 30 else None

def stochastic_rsi_kd(df, period=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    stoch_k = ((rsi - rsi.rolling(14).min()) / (rsi.rolling(14).max() - rsi.rolling(14).min())) * 100
    stoch_d = stoch_k.rolling(3).mean()
    return stoch_k, stoch_d

def is_rebound_signal(df):
    if df is None or len(df) < 30:
        return False

    ma200 = df['close'].rolling(200).mean()
    current_price = df['close'].iloc[-1]
    prev_price = df['close'].iloc[-2]

    # 이평선 위에 있고, 최근 눌림 후 양봉 전환
    price_above_ma = current_price > ma200.iloc[-1]
    bullish_candle = current_price > df['open'].iloc[-1] and prev_price < df['open'].iloc[-2]

    # Stochastic RSI 반등 구간 (골든크로스 또는 과매도 반등)
    k, d = stochastic_rsi_kd(df)
    stoch_rebound = k.iloc[-2] < d.iloc[-2] and k.iloc[-1] > d.iloc[-1] and k.iloc[-1] < 30

    return price_above_ma and bullish_candle and stoch_rebound

def execute_buy(market):
    last_trade_time[market] = time.time()
    price = safe_get_current_price(market)
    if price == 0:
        return
    volume = TRADE_AMOUNT / price
    res = upbit.buy_market_order(market, TRADE_AMOUNT)
    if 'uuid' in res:
        now_time = datetime.datetime.now().strftime('%H:%M')
        name = market.split('-')[1]
        now_full = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print(f"[{now_time}] [매수: {name}] {TRADE_AMOUNT:,}원 매수")
        send_slack_alert(f"[{now_time}] [매수: {name}] {TRADE_AMOUNT:,}원 매수")

        log_to_csv([now_full, market, "BUY", price, volume, "-", "추세반등"])
        trade_count[market] += 1

# === 메인 루프 ===
print("\U0001F504 추세 반등 매매 봇 시작됨")
send_slack_alert("\U0001F504 추세 반등 매매 봇 시작됨")

while True:
    try:
        top_symbols = get_top_20_symbols()
        for market in top_symbols:
            df = fetch_recent_prices(market)
            if check_can_trade(market) and is_rebound_signal(df):
                execute_buy(market)
        time.sleep(60)
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print("[오류 발생]", err_msg)
        send_slack_alert(f"[오류 발생]\n{err_msg}")
        time.sleep(30)
