FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN apk add gcc bash musl-dev git libffi-dev npm

COPY . /app
WORKDIR /app

# allows git to work with the directory, making commands like /about better
RUN git config --global --add safe.directory /app

RUN uv sync

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# no idea why we can't use uv run, but oh well
RUN python -m prisma generate

CMD [ "python", "main.py" ]