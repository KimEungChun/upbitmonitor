#!/bin/bash

echo "🚀 코드 최신화 중..."
cd ~/upbitmonitor || { echo "❌ 디렉토리 이동 실패"; exit 1; }
git pull origin main

echo "📦 exporter 재빌드 및 재시작"
docker stop upbit-exporter 2>/dev/null && docker rm upbit-exporter 2>/dev/null
docker build -t monitoring-exporter ./exporter
docker run -d --name upbit-exporter -p 8000:8000 monitoring-exporter

echo "🔁 Prometheus 재시작 (systemd)"
sudo systemctl restart prometheus

echo "🧠 Grafana는 설정 변경이 없으므로 재시작 생략"

echo "✅ 배포 완료!"
