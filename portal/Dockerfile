# Playwright image: Chromium is needed by tools/make_cover.py (the cover page step).
FROM mcr.microsoft.com/playwright/python:v1.59.0-noble
WORKDIR /srv
COPY portal/requirements.txt ./portal/requirements.txt
RUN pip install --no-cache-dir -r portal/requirements.txt pypdf
COPY tools ./tools
COPY portal/app ./portal/app
WORKDIR /srv/portal
ENV DATA_DIR=/srv/data
ENV COVER_COMMAND="python3 ../tools/make_cover.py {input} {output} --meta {meta}"
VOLUME ["/srv/data"]
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
