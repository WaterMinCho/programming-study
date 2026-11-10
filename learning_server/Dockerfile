FROM python:3.12-slim
WORKDIR /app
COPY learning_server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY learning_server /app/learning_server
COPY aiprep/__init__.py aiprep/collection.py aiprep/goals.py aiprep/sharing.py /app/aiprep/
RUN useradd --create-home --uid 10001 collector && mkdir /data && chown collector:collector /data
USER collector
ENV STUDY_DATA_DB=/data/learning.sqlite3 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8765
CMD ["waitress-serve", "--listen=0.0.0.0:8765", "--threads=4", "--max-request-body-size=1048576", "--channel-timeout=30", "--no-expose-tracebacks", "learning_server.wsgi:application"]
