# 项目概述  
这是一个集成的语音交互小助手，能够实时与大模型进行交互并通过VAD进行打断。目前使用的asr是Sensevoice，LLM可以使用任何符合OpenAI输出格式的大模型，TTS使用的是FishSpeech。  
ASR以及TTS都是开源的。部署在A40机器上的延迟在1s左右，如何部署在A100机器上，估计延迟可以在600ms。  

### 前提条件  

首先，要部署成功SenseVoice和和FishSpeech  

SenseVoice地址：https://github.com/FunAudioLLM/SenseVoice  

FishSpeech地址：https://github.com/fishaudio/fish-speech  

然后，根据server下的readme进行操作，同理web端，按照web端下的readme操作即可。  

### 流程如图所示   

![流程图](https://github.com/FreedomIntelligence/Intelligent-Voice-Assistant/blob/main/img/%E6%B5%81%E7%A8%8B%E5%9B%BE.png)  

### 模块介绍

上述的图片表述的是从前端接受到语音的一段音频经过流程处理成语音再上传前端的过程。实现的逻辑是通过定义各个队列进行传输实现的。主要包括5个模块的处理来实现的，下面介绍一下各个模块的基本功能：  

- audio_detection模块：该模块主要进行语音检测的功能，以及VAD检测的部分。

- audio_procession模块：该模块主要将audio_detection_queue队列中的数据进行处理，其中包括发送给ASR进行处理，处理的结果放在send_text_queue队列发给前端和LLM模型进行处理，LLM处理的结果传给text_queue队列。

- text_procession模块：该模块主要进行对文本进行分割处理，处理的结果分别放在tts_queue和send_text_queue队列。

- tts_model模块：该模块主要将分割后的文本发送给TTS进行处理，TTS处理后的结果直接放在send_audio_queue队列。

- data_transmission模块：该模块主要将send_text_queue和send_audio_queue队列发送给前端。

### 注意：

各个模块并不是顺序进行的，模块是异步的
岁色大辞典

