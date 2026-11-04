"""Exercise a downloaded backend image using only disposable container data."""
import json
import os
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

def request(path, data=None, token=None, form=False):
    headers = {}
    if data is not None:
        data = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request("http://127.0.0.1:8000" + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)

with tempfile.TemporaryDirectory(prefix="careertracker-smoke-") as directory:
    os.environ.update(
        DATABASE_URL="sqlite:///" + directory + "/smoke.db",
        JWT_SECRET_KEY=secrets.token_hex(32),
        PYTHON_DOTENV_DISABLED="1",
        APP_ENV="production",
        REGISTRATION_ENABLED="true",
    )
    subprocess.run(["python", "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run(["python", "-m", "alembic", "check"], check=True)
    server = subprocess.Popen(
        ["python", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-access-log"],
        stdout=subprocess.DEVNULL,
    )
    try:
        for attempt in range(60):
            if server.poll() is not None:
                raise RuntimeError("Server exited before readiness")
            try:
                code, body = request("/")
                assert code == 200 and body["message"] == "CareerTracker is running."
                break
            except urllib.error.URLError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Server readiness timed out")
        assert request("/auth/me")[0] == 401
        email = "container-smoke@example.com"
        password = secrets.token_urlsafe(24)
        code, user = request("/auth/register", {"email": email, "password": password})
        assert code == 201 and user["email"] == email
        assert request("/auth/token", {"username": email, "password": "incorrect-password"}, form=True)[0] == 401
        code, result = request("/auth/token", {"username": email, "password": password}, form=True)
        assert code == 200
        token = result["access_token"]
        code, current = request("/auth/me", token=token)
        assert code == 200 and current["id"] == user["id"]
        code, records = request("/opportunities", token=token)
        assert code == 200 and records == []
        print("PASS: migrations, readiness, anonymous 401, registration, wrong-password 401, login, identity, empty CRM list")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
