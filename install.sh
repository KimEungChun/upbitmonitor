#!/bin/bash

# 설치 전 준비
sudo apt update -y
sudo apt install -y wget curl unzip

# Prometheus 설치
PROM_VERSION="2.52.0"
wget https://github.com/prometheus/prometheus/releases/download/v$PROM_VERSION/prometheus-$PROM_VERSION.linux-amd64.tar.gz
tar xvf prometheus-$PROM_VERSION.linux-amd64.tar.gz
sudo mv prometheus-$PROM_VERSION.linux-amd64 /etc/prometheus
sudo ln -s /etc/prometheus/prometheus /usr/local/bin/prometheus

# 사용자 및 서비스 설정
sudo useradd --no-create-home --shell /usr/sbin/nologin prometheus
sudo mkdir -p /etc/prometheus /var/lib/prometheus
sudo cp /etc/prometheus/prometheus.yml /etc/prometheus/prometheus.yml.bak
sudo tee /etc/systemd/system/prometheus.service > /dev/null <<EOF
[Unit]
Description=Prometheus
After=network.target

[Service]
User=prometheus
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus

[Install]
WantedBy=multi-user.target
EOF

# Grafana 설치
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
sudo apt update
sudo apt install -y grafana

# 서비스 시작 및 자동 실행 설정
sudo systemctl daemon-reexec
sudo systemctl enable prometheus
sudo systemctl start prometheus

sudo systemctl enable grafana-server
sudo systemctl start grafana-server
