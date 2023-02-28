FROM python:3.10-slim

RUN apt-get update && apt-get install -y python3-tk && pip install --upgrade pip

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY loom loom

COPY pyproject.toml pyproject.toml
COPY README.md README.md
RUN pip install -e .

ENTRYPOINT ["python", "loom/main.py"]
