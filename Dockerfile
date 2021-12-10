FROM gradle:jdk11

RUN apt update && apt upgrade -y

RUN apt install -y -q build-essential python3-pip python3-dev

RUN pip3 install -U pip setuptools wheel
RUN pip3 install gunicorn uvloop httptools

COPY requirements.txt /app/requirements.txt

RUN pip3 install -r /app/requirements.txt

COPY app/ /app

WORKDIR /app/core/grobid

ADD --chown=gradle:gradle /app/core /app

RUN apt-get install dos2unix

RUN cd /app/core/grobid
RUN dos2unix ./gradlew
RUN ./gradlew clean install --no-daemon --stacktrace

# SUPER RUN
# Start grobid

#ENTRYPOINT /
RUN cd /app/core/grobid
RUN ./gradlew
WORKDIR /



# SUPER RUN
# Starts the server as a gunicorn server under the ip-adress 0.0.0.0:80 with 4 workers
#RUN /usr/local/bin/gunicorn \
#  -b 0.0.0.0:80 \
#  -w 4 \
#  -k uvicorn.workers.UvicornWorker main:app \
#  --chdir /app



