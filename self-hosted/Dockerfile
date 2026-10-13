FROM ghcr.io/dgtlmoon/changedetection.io:0.60.9
COPY start.py /app/railway-start.py
ENV PORT=5000 \
    LISTEN_HOST=0.0.0.0 \
    FETCH_WORKERS=1 \
    MINIMUM_SECONDS_RECHECK_TIME=900 \
    LLM_FEATURES_DISABLED=true \
    TZ=America/Los_Angeles
ENTRYPOINT ["python", "/app/railway-start.py"]
