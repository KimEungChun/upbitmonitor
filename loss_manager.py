# profit_loss_manager.py

import time
from datetime import datetime
from dotenv import load_dotenv
import os
import requests
import pyupbit

# 환경 변수 로드
load_dotenv()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)

# ===== 설정 =====
PROFIT_THRESHOLD = 2.0        # 익절 기준 +2%
TRAILING_STOP = 0.5           # 트레일링 스탑 -0.5%
LOSS_THRESHOLD = -1.0         # 손절 기준 -1%
MIN_SELL_KRW = 5000           # 최소 매도 가능 금액
PARTIAL_SELL_COOLDOWN = 300   # 분할 손절 쿨다운 (초)

# 상태 저장
last_partial_sell_time = {}
max_price = {}

# ===== 유틸 =====
def log(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")
    with open("auto_trade.log", "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {msg}\n")

def send_slack_alert(msg):
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": msg})
    except Exception as e:
        log(f"Slack 전송 실패: {e}")

def execute_sell(symbol, volume, price):
    try:
        order = upbit.sell_market_order(symbol, volume)
        name = symbol.split('-')[1]
        now = datetime.now().strftime("[%H:%M]")
        total = price * volume if price else 0

        log(f"{now} 💸 매도 실행: {symbol} | 수량: {volume:.4f}개 | 현재가: {price:.2f} | 예상금액: {total:,.0f}원")
        send_slack_alert(f"{now} 💸 *{name} 매도 완료*\n수량: {volume:.4f}개 | 현재가: {price:.2f}원\n→ 약 {total:,.0f}원")

    except Exception as e:
        log(f"❌ {symbol} 실매도 실패: {e}")

# ===== 핵심 손익절 로직 =====
def manage_profit_loss(data_pool):
    holdings = data_pool.get_holdings()
    now = time.time()

    for symbol in holdings:
        price = data_pool.get_price(symbol)
        avg_buy = data_pool.get_avg_buy_price(symbol)
        balance = data_pool.get_balance(symbol)

        if not price or not avg_buy or balance == 0:
            continue

        profit_pct = ((price - avg_buy) / avg_buy) * 100

        # 최고가 갱신
        if symbol not in max_price or price > max_price[symbol]:
            max_price[symbol] = price

        drop_pct = ((max_price[symbol] - price) / max_price[symbol]) * 100

        name = symbol.split('-')[1]
        log(f"🔍 {name} 손익률: {profit_pct:.2f}%, 하락폭: {drop_pct:.2f}%")

        # 익절: 수익 +2% 이상 + 하락폭 -0.5% 이상
        if profit_pct >= PROFIT_THRESHOLD and drop_pct >= TRAILING_STOP:
            msg = f"✅ {name} 익절 매도 (평단: {avg_buy:.2f}, 현재: {price:.2f}, 수익률: {profit_pct:.2f}%)"
            log(msg)
            send_slack_alert(msg)
            execute_sell(symbol, balance, price)
            max_price.pop(symbol, None)
            continue

        # 손절: 손실 -1% 이하
        if profit_pct <= LOSS_THRESHOLD:
            if symbol not in last_partial_sell_time or now - last_partial_sell_time[symbol] >= PARTIAL_SELL_COOLDOWN:
                if balance * price >= MIN_SELL_KRW:
                    partial_volume = balance * 0.5
                    execute_sell(symbol, partial_volume, price)
                    last_partial_sell_time[symbol] = now
                else:
                    log(f"⚠️ {name} 손절 대상 금액 너무 작음 (미매도) [{balance}개]")
            else:
                log(f"❗ {name} 손절 쿨다운 진행 중")
