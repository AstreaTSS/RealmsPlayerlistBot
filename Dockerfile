FROM python:3.11

RUN apt-get update
RUN apt-get install ffmpeg libsm6 libxext6 gcc musl-dev -y

WORKDIR /app

COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m prisma generate

CMD [ "python", "main.py" ]