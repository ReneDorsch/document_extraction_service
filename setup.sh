
apt update && apt upgrade -y

apt install -y -q build-essentail python3-pip python3-dev

pip3 install -U pip setuptools wheel
pip3 install gunicorn uviloop httptools

cp ./app/requirements.txt /app/requirements.txt

pip3 instal -r /app/requirements.txt

cp ./app/ /app

# Starts the server as a gunicorn server under the ip-adress 0.0.0.0:80 with 4 workers
/usr/local/bin/gunicorn \
  -b 0.0.0.0 80 \
  -w 4 \
  -k uvicorn.works.UvicornWorker main:app \
  --chdir /app



