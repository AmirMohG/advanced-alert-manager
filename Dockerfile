from docker-mirror.kubarcloud.com/python:3.9

copy . .

run pip install -r requirements.txt

cmd ["python3", "main.py"]