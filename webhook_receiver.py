from flask import Flask, request
import os
import subprocess

app = Flask(__name__)

@app.route("/trigger", methods=["POST"])
def trigger_deploy():
    # 로그용 출력
    print("🚀 Webhook 수신 → 배포 시작")
    
    # 배포 명령 실행 (비동기)
    subprocess.Popen("cd ~/upbitmonitor && git pull origin main && ./deploy.sh", shell=True)
    return "✅ Deploy triggered", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
