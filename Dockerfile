FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN apk add gcc bash musl-dev git libffi-dev npm

COPY . /app
WORKDIR /app

# allows git to work with the directory, making commands like /about better
RUN git config --global --add safe.directory /app

RUN uv pip install --system -r requirements.txt
RUN python -m prisma generate

CMD [ "python", "main.py" ]