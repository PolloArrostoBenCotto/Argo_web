@echo off
cd C:\Users\rosse\Desktop\Argo_web\v1.1
echo Starting App
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload