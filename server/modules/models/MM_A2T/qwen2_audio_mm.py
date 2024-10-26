import asyncio
import aiohttp
import json
import time
import librosa
import soundfile as sf
import io
import logging
from pathlib import Path
from transformers import AutoProcessor
from models.MM_A2T.base_mm import BaseMM

# 配置日志记录
current_dir = Path(__file__).resolve().parent
log_dir = current_dir.parents[2]
log_file_path = log_dir / 'log.txt'
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Qwen2AudioMM(BaseMM):
    def __init__(self, session: aiohttp.ClientSession):
        """
        初始化 Qwen2AudioMM 实例。
        """
        self.model_path = '/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/workspace/qwen2_audio_instruct/Qwen/Qwen2-Audio-7B-Instruct'
        self.api_url = "http://172.24.168.28:8084/v1/chat/completions"
        self.temperature = 0.7
        self.session = session
        self.processor = self.load_processor(self.model_path)
        self.audio_dir = '/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/server/test/'
        logging.info("Qwen2AudioMM 实例已初始化。")
    
    def load_processor(self, model_path):
        """
        加载AutoProcessor。

        :param model_path: 模型的路径。
        :return: 加载的processor对象。
        """
        start_time = time.time()
        processor = AutoProcessor.from_pretrained(model_path)
        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info(f"Processor加载时间: {elapsed_time:.4f} 秒")
        return processor
        
    async def post_audio(self, combined_audio: bytes, lang: str = "auto") -> str:
        """
        将接收到的音频字节转换为WAV格式并保存到指定文件夹中。

        :param combined_audio: 音频的字节数据。
        :param lang: 语言参数（未使用，保留接口一致性）。
        :return: 保存的WAV文件路径。
        """
        wav_path = self._convert_to_wav(combined_audio)
        return wav_path  # 返回WAV文件路径字符串
    
    def _convert_to_wav(self, combined_audio: bytes) -> str:
        """
        将音频字节转换为WAV格式并保存到指定文件夹中。

        :param combined_audio: 音频的字节数据。
        :return: 保存的WAV文件路径。
        """
        timestamp = int(time.time())
        wav_filename = f"audio_{timestamp}.wav"
        wav_path = Path(self.audio_dir) / wav_filename
        
        audio_buffer = io.BytesIO(combined_audio)
        try:
            audio_data, sr = librosa.load(audio_buffer, sr=None)
            sf.write(str(wav_path), audio_data, sr)
            logging.info(f"已保存WAV文件到 {wav_path}")
        except Exception as e:
            logging.error(f"音频转换失败: {e}")
            raise e
        return str(wav_path)
        
    def build_payload(self, conversation, new_message):
        """
        构建API请求所需的payload数据。

        :param conversation: 对话历史，包含用户和助手的消息。
        :param new_message: 新的用户消息，包含文本和音频。
        :return: 构建好的payload字典。
        """
        # 从history_queue重建对话历史
        messages = []
        for msg in conversation:
            if isinstance(msg["content"], list):
                for ele in msg["content"]:
                    if ele["type"] == "audio":
                        messages.append({
                            "content": ele['audio_url'],
                            "role": "user",
                            "name": "string"
                        })
                    elif ele["type"] == "text":
                        messages.append({
                            "content": ele['text'],
                            "role": "user",
                            "name": "string"
                        })
            else:
                messages.append({
                    "content": msg['content'],
                    "role": msg['role'],
                    "name": "string"
                })
        
        # 添加新的消息
        for ele in new_message:
            if ele["type"] == "audio":
                messages.append({
                    "content": ele['audio_url'],
                    "role": "user",
                    "name": "string"
                })
            elif ele["type"] == "text":
                messages.append({
                    "content": ele['text'],
                    "role": "user",
                    "name": "string"
                })
        
        # 构建API请求的payload
        payload = {
            "messages": messages,
            "model": 'qwen2_audio',
            "temperature": self.temperature,
            "stream": True,
        }
        return payload
        
    async def post_text(self, wav_path, text_queue: asyncio.Queue, history_queue: asyncio.Queue, max_history_num=0):
        """
        使用构建的payload与模型进行通信，处理模型的响应并更新队列。

        :param new_message: 新的用户消息。
        :param text_queue: 用于存储模型响应文本的异步队列。
        :param history_queue: 用于存储对话历史的异步队列，最多保留最新的max_history_num条记录。
        :param max_history_num: 历史记录的最大数量，默认为0。
        """
        # 从history_queue重建对话历史
        conversation = []
        while not history_queue.empty():
            conversation.append(history_queue.get_nowait())
        
        # 构建payload
        # new_message = [{"type": "audio", "audio_url": wav_path}, {"type": "text", "text": "这段音频内容是什么？"}]
        new_message = [{"type": "audio", "audio_url": '/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/workspace/test/vllm/vllm/entrypoints/openai/tools/throatclearing.wav'}, {"type": "text", "text": "这段音频内容是什么？"}]
        # new_message = [{"type": "audio", "audio_url": 'https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen2-Audio/audio/f2641_0_throatclearing.wav'}, {"type": "text", "text": "这段音频内容是什么？"}]
        payload = self.build_payload(conversation, new_message)
        
        headers = {'Content-Type': 'application/json'}
        
        try:
            async with self.session.post(self.api_url, headers=headers, data=json.dumps(payload)) as response:
                if response.status != 200:
                    logging.error(f"API请求错误，状态码: {response.status}")
                    await text_queue.put(None)
                    return
                # 处理流式响应
                result = ""
                start_time = time.time()
                first_few = 10  # 控制打印前几个回复的时间
                count = 0
                async for line in response.content:
                    if not line:
                        continue
                    decoded_line = line.decode('utf-8').strip()
                    if decoded_line.startswith("data: "):
                        decoded_line = decoded_line[len("data: "):]
                    if decoded_line == "[DONE]":
                        break
                    try:
                        json_data = json.loads(decoded_line)
                        content = json_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            result += content
                            count += 1
                            await text_queue.put(content)
                            if count <= first_few:
                                elapsed_time = time.time() - start_time
                                logging.info(f"从发送请求到第{count}个回复消耗时间: {elapsed_time:.4f} 秒")
                    except json.JSONDecodeError:
                        logging.error(f"无法解析的JSON: {decoded_line}")
                # await text_queue.put(result)
                # 更新history_queue
                conversation.append({"role": "assistant", "content": result})
                if max_history_num > 0:
                    conversation = conversation[-max_history_num:]
                for msg in conversation:
                    await history_queue.put(msg)
        except Exception as e:
            logging.error(f"请求失败: {e}")
            await text_queue.put(None)
        
    async def close(self):
        """
        关闭HTTP会话。
        """
        await self.session.close()
        self.session = aiohttp.ClientSession()

if __name__ == "__main__":
    async def main(session):
        client = Qwen2AudioMM(session)
        ##################################################
        # 定义对话历史
        history = [
            # {
            #     "role": "user",
            #     "content": [
            #         {"type": "audio", "audio_url": "/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/output_file.wav"},
            #         {"type": "text", "text": "Hello! Can you hear this sound?"},
            #     ]
            # },
            # {
            #     "role": "assistant",
            #     "content": "Yes, I can."
            # }
        ]
        history_queue = asyncio.Queue()
        for msg in history:
            await history_queue.put(msg)
        ##################################################
        # 测试post_audio
        # wav_file_path = "/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/server/output.wav"
        # try:
        #     with open(wav_file_path, 'rb') as f:
        #         audio_bytes = f.read()
        # except Exception as e:
        #     print(f"读取 WAV 文件时发生错误: {e}")
        #     return  # 退出main函数
        
        # wav_path = await client.post_audio(audio_bytes)
        # print(f"保存的WAV文件路径: {wav_path}")
        ##################################################
        # 测试post_text
        # {"type": "audio", "audio_url": "/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/output_file.wav"},
        wav_file_path = 'https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen2-Audio/audio/glass-breaking-151256.mp3'
        new_message = [
            {"type": "audio", "audio_url": wav_file_path},  # 修正类型为 "audio"
            {"type": "text", "text": "这段音频的内容是什么？"}
        ]
        text_queue = asyncio.Queue()
        print('start')
        await client.post_text(new_message, text_queue, history_queue)
        
        # 获取响应
        response = await text_queue.get()
        print("响应内容:", response)
        # await client.close()
        
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"主函数执行失败: {e}")
        
    session = aiohttp.ClientSession
    asyncio.run(main(session))
