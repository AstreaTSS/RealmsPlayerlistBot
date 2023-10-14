FROM python:3.12-alpine

RUN apk add --no-cache gcc bash musl-dev

WORKDIR /app

COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m prisma generate

CMD [ "python", "main.py" ]