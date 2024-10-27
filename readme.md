# 项目概述  
这是一个集成的语音交互小助手，能够实时与大模型进行交互。目前使用的asr是Sensevoice，LLM可以使用任何符合OpenAI输出格式的大模型，TTS使用的是FishSpeech。  
ASR以及TTS都是开源的。部署在A40机器上的延迟在1s左右，如何部署在A100机器上，估计延迟可以在600ms。  

### 前提条件  

首先，要部署成功SenseVoice和和FishSpeech  

SenseVoice地址：https://github.com/FunAudioLLM/SenseVoice  

FishSpeech地址：https://github.com/fishaudio/fish-speech  

然后，根据server下的readme进行操作，同理web端，按照web端下的readme操作即可。  

### 流程如图所示   

![流程图](https://github.com/FreedomIntelligence/Intelligent-Voice-Assistant/blob/main/img/%E6%B5%81%E7%A8%8B%E5%9B%BE.png)  

上述的图片表述的是从前端接受到语音的一段音频经过流程处理成语音再上传前端的过程，实


