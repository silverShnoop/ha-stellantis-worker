# Pinned to bookworm (Debian 12), not the floating -slim tag. That tag has
# rolled on to trixie, which Playwright 1.49 did not recognise: it fell back
# to an Ubuntu 20.04 package list naming ttf-ubuntu-font-family and
# ttf-unifont, neither of which exists on Debian, and the install exited 100.
# Playwright 1.63 does list debian13, but nobody has built this image there
# yet, so debian12 it stays. Revisit when there is a reason to rebuild.
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --only-shell fetches chromium-headless-shell rather than full Chromium:
# 116 MB against 208 MB compressed on arm64, for the revision 1.63 pins. The
# worker only ever calls launch(headless=True), which is exactly what the
# shell serves; it can do nothing headed, which this never asks for. It does
# not shrink the apt set — Playwright keeps one dependency list per browser,
# not per build, so the shell pulls the same packages Chromium would.
#
# --with-deps lets Playwright choose those libraries itself, rather than a
# hand-listed apt set that drifts as Debian renames packages (libasound2
# became libasound2t64 in trixie, which silently breaks such a list).
RUN playwright install --with-deps --only-shell chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

COPY main.py run.sh .

# The worker runs as an unprivileged user, not root. Chromium still needs
# --no-sandbox: its own sandbox wants user namespaces, which Supervisor's
# Docker does not hand out. So the user drop is the mitigation instead —
# whatever gets out of the renderer is uid 1000 in a container with nothing
# in it. The drop happens in run.sh rather than with USER here, because
# Supervisor writes /data/options.json root-only and the options have to be
# read before the privileges go.
RUN useradd --uid 1000 --user-group --create-home --shell /usr/sbin/nologin worker \
    && chmod -R a+rX /ms-playwright \
    && chown -R worker:worker /app

# Opens the port on Docker's internal network only. There is deliberately no
# ports mapping in config.yaml, so Supervisor publishes nothing to the host
# and the LAN cannot reach this.
EXPOSE 3000

CMD ["./run.sh"]
