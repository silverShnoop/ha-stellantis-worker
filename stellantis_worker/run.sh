#!/bin/sh
# Supervisor writes /data/options.json root-only (mode 0600), so a process
# that has already dropped to the unprivileged user cannot read it. Read it
# here, as root, hand it to the worker in its environment, then drop.
set -eu
if [ -r /data/options.json ]; then
    WORKER_OPTIONS="$(cat /data/options.json)"
    export WORKER_OPTIONS
fi
exec setpriv --reuid=worker --regid=worker --init-groups \
    uvicorn main:app --host 0.0.0.0 --port 3000
