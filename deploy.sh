#!/bin/bash

echo "🚀 코드 최신화 중..."
cd ~/upbitmonitor || { echo "❌ 디렉토리 이동 실패"; exit 1; }
git pull origin main

echo "📦 exporter 재빌드 및 재시작"
docker stop upbit-exporter 2>/dev/null && docker rm upbit-exporter 2>/dev/null
docker build -t monitoring-exporter ./exporter
docker run -d --name upbit-exporter -p 8000:8000 monitoring-exporter

echo "🔁 Prometheus 컨테이너 재시작 또는 실행"
docker stop prometheus 2>/dev/null && docker rm prometheus 2>/dev/null
docker run -d --name prometheus \
  -p 9090:9090 \
  -v ~/upbitmonitor/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

echo "📊 Grafana 컨테이너 재시작 또는 실행"
docker stop grafana 2>/dev/null && docker rm grafana 2>/dev/null
docker run -d --name grafana \
  -p 3000:3000 \
  grafana/grafana

echo "✅ 모든 서비스가 Docker 컨테이너로 재배포 완료!"
