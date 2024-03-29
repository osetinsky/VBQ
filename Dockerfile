FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy only the requirements.txt file and install Python dependencies
# This avoids reinstalling requirements every time the script changes
COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]