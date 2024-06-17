FROM python:3.12-alpine

RUN apk add gcc bash musl-dev git libffi-dev npm curl
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

COPY . /app

# allows git to work with the directory, making commands like /about better
RUN git config --global --add safe.directory /app

RUN /root/.cargo/bin/uv pip install --system -r requirements.txt
RUN python -m prisma generate

CMD [ "python", "main.py" ]