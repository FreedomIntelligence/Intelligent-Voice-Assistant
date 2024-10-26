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

### 4.更改配置  

#### 4.1 更改ASR，LLM，TTS。（默认ASR：SenseVoice，LLM：符合OpenAI的输出格式即可，TTS：FishSpeech）  
```bash
ASR：直接更改Sense_asr下的url,如果想添加其他的asr,只要有满足base_asr下的要求即可  

LLM：直接更改deepspeek_llm下的url以及model名称，如果不是OpenAI的输出格式，需要添加额外的LLM，可根据base_llm下的要求添加即可，eg:qwen_llm  

TTS: 更改fish_speech_tts下的URL外，还需要更改refereence_audio和reference_text(这里的语音需要满足音频的评率是44100，如果是48000或者其他，只需要在Fish运行api脚本文件中的，sample_rate更改你想要的即可)。同理，想要添加其他的TTS，只需满足base_tts下的要求即可。
```  

#### 4.2 更改模块间参数
```bash

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
