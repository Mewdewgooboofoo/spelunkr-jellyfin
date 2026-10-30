
FROM python:3.12-slim



WORKDIR /updater



COPY update.py /updater/update.py



ENV TZ=UTC



CMD ["sh", "-c", "while true; do python -u /updater/update.py; sleep 86400; done"]

