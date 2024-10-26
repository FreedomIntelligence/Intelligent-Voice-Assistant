# 🚀 服务器部署指南

## 📦 前提条件

- 已安装 Conda
- 已安装 Python 3.10

## 🛠️ 步骤

### 1. 创建虚拟环境

```bash
conda create -n server python=3.10
```

### 2. 激活虚拟环境

```bash
conda activate server
```

### 3. 安装依赖包

```bash
pip install -r requirements.txt
pip install 'uvicorn[standard]'
```

### 4. 指定GPU运行（可选）

```bash
CUDA_VISIBLE_DEVICES=1 python python.py
```

### 5. 以HTTPS协议部署服务器

#### 生成SSL证书（可使用部署https的web时生成的证书）

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

#### 运行项目

```bash
uvicorn server:app --host 172.24.168.23 --port 8000 --ssl-keyfile=/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/fastapi_project/key.pem --ssl-certfile=/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/fastapi_project/cert.pem
```