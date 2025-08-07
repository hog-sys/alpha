web: gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.web.dashboard_server:app --bind 0.0.0.0:$PORT
worker: python main.py