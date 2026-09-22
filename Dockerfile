FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock
COPY services services
COPY sentinel sentinel
COPY tests tests
COPY web web
RUN useradd -m sentinel && mkdir /work && chown sentinel /work
USER sentinel
CMD ["uvicorn", "services.app:app", "--host", "0.0.0.0", "--port", "8000"]
