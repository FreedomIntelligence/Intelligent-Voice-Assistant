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
CUDA_VISIBLE_DEVICES=1 XXXXXX
```

### 5. 以HTTPS协议部署服务器

#### 生成SSL证书（可使用部署https的web时生成的证书）

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

#### 运行项目

```bash
uvicorn server:app --host 1XX.XXX.XXX.XXX --port 8000 --ssl-keyfile=XXX/key.pem --ssl-certfile=XXX/cert.pem
```
