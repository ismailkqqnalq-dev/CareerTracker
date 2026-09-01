FROM python:3.12-slim

WORKDIR /app
COPY . .

CMD ["python", "careertracker/app/main.py"]
