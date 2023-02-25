FROM python:3.10-slim

RUN apt-get update && apt-get install -y python3-tk && pip install --upgrade pip

WORKDIR /app

COPY . ./

RUN pip install -r requirements.txt

CMD ["python", "main.py"]
