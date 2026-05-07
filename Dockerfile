FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

COPY bondcalc.py /app/bondcalc.py
COPY molecules.json /app/molecules.json
COPY aggregate.py /app/aggregate.py
WORKDIR /app

ENTRYPOINT ["python", "bondcalc.py"]
