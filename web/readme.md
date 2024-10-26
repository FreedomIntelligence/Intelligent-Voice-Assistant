# 🚀 服务器部署指南

## 📦 前提条件

- 已安装 Conda
- 已安装 Python 3.10

## 🛠️ 步骤

### 1. 通过HTTPS协议运行

#### 1.1 生成SSL证书

在通过HTTPS协议运行项目之前，请确保根目录下存在`key.pem`和`cert.pem`文件。如果这些文件不存在，请使用以下命令生成自签名证书：

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

#### 1.2 运行项目

生成证书后，使用以下命令通过HTTPS协议运行项目：

```bash
uvicorn main:app --host 172.24.168.23 --port 8088 --reload --ssl-keyfile=./key.pem --ssl-certfile=./cert.pem
```
