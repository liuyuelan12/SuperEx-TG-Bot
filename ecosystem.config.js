module.exports = {
    apps: [{
        name: "tg-sender",
        script: "./sender.py",
        interpreter: "./venv/Scripts/python.exe",
        args: "--loop",
        autorestart: true,
        watch: false,
        env: {
            PYTHONUNBUFFERED: "1"
        }
    }, {
        name: "tg-api",
        script: "./venv/Scripts/uvicorn.exe",
        args: "web_manager:app --host 0.0.0.0 --port 8000",
        interpreter: "none",
        autorestart: true
    }, {
        name: "tg-web",
        script: "npm",
        args: "start",
        cwd: "./web-manager",
        env: {
            PORT: "3000"
        }
    }]
}
