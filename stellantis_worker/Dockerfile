FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --with-deps lets Playwright choose the system libraries its own build needs,
# rather than a hand-listed apt set that drifts as Debian renames packages
# (libasound2 became libasound2t64 in trixie, which silently breaks the list).
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY main.py .

EXPOSE 3000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
