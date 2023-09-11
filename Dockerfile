FROM python:3.11-alpine

RUN apk add --no-cache gcc bash

WORKDIR /app

COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m prisma generate

CMD [ "python", "main.py" ]