FROM python:3.12-alpine

RUN apk add --no-cache gcc bash musl-dev git

WORKDIR /app

COPY . /app

# allows git to work with the directory, making commands like /about better
RUN git config --global --add safe.directory /app

RUN pip install --no-cache-dir -r requirements.txt
RUN python -m prisma generate

CMD [ "python", "main.py" ]