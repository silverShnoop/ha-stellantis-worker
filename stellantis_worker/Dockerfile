# Pinned to bookworm (Debian 12), not the floating -slim tag. That tag has
# rolled on to trixie, which Playwright 1.49 does not recognise: it falls back
# to an Ubuntu 20.04 package list naming ttf-ubuntu-font-family and
# ttf-unifont, neither of which exists on Debian, and the install exits 100.
# Playwright knows debian11 and debian12 only, so debian12 it is. Revisit when
# a Playwright release adds trixie.
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --only-shell fetches chromium-headless-shell rather than full Chromium:
# 103 MB against 165 MB compressed. The worker only ever calls
# launch(headless=True), which is exactly what the shell serves; it can do
# nothing headed, which this never asks for. It does not shrink the apt set —
# Playwright keeps one dependency list per browser, not per build, so the
# shell pulls the same 21 packages Chromium would.
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
