# Upbit exporter source will go here
from flask import Flask, Response
import requests

app = Flask(__name__)

def get_top_krw_markets(limit=20):  # 수정된 부분: limit 기본값 20
    # 1. 전체 KRW 마켓 가져오기
    market_url = "https://api.upbit.com/v1/market/all"
    market_data = requests.get(market_url).json()
    krw_markets = [m['market'] for m in market_data if m['market'].startswith("KRW-")]

    # 2. 해당 마켓들의 ticker 정보 조회
    ticker_url = f"https://api.upbit.com/v1/ticker?markets={','.join(krw_markets)}"
    ticker_data = requests.get(ticker_url).json()

    # 3. 24시간 거래금 기준 정렬 후 상위 limit개
    sorted_data = sorted(ticker_data, key=lambda x: x['acc_trade_price_24h'], reverse=True)
    return sorted_data[:limit]

@app.route("/metrics")
def metrics():
    top_data = get_top_krw_markets(20)  # 수정된 부분: 20개 사용
    output = "# HELP upbit_price 업비 가격\n"
    output += "# TYPE upbit_price gauge\n"

    for item in top_data:
        symbol = item['market'].split("-")[1]
        price = item['trade_price']
        volume = item['acc_trade_price_24h']

        output += f'upbit_price{{symbol="{symbol}"}} {price}\n'
        output += f'upbit_volume_24h{{symbol="{symbol}"}} {volume}\n'

    return Response(output, mimetype='text/plain')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)