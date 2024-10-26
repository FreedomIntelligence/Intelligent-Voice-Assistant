from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

app = FastAPI()

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 设置模板目录
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("/index.html", {"request": request})

# uvicorn main:app --host 172.24.162.115 --port 8088 --reload
# openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
# CUDA_VISIBLE_DEVICES= uvicorn main:app --host 10.27.127.33 --port 8001 --reload --ssl-keyfile=./key.pem --ssl-certfile=./cert.pem