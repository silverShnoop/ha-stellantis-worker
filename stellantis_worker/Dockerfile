FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --only-shell fetches chromium-headless-shell rather than full Chromium:
# 103 MB against 165 MB compressed, and a smaller system-library set with it,
# because the shell needs no GTK, X11 or audio stack. The worker only ever
# calls launch(headless=True), which is exactly what the shell serves; it can
# do nothing headed, which this never asks for.
#
# --with-deps lets Playwright choose those libraries itself, rather than a
# hand-listed apt set that drifts as Debian renames packages (libasound2
# became libasound2t64 in trixie, which silently breaks such a list).
RUN playwright install --with-deps --only-shell chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

COPY main.py .

# Opens the port on Docker's internal network only. There is deliberately no
# ports mapping in config.yaml, so Supervisor publishes nothing to the host
# and the LAN cannot reach this.
EXPOSE 3000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
