import asyncio
import aiohttp
import json
import time
import librosa
import soundfile as sf
import io
import os
import logging
from pydub import AudioSegment
from pathlib import Path
from transformers import AutoProcessor
from models.MM_A2T.base_mm import BaseMM
import base64
from openai import OpenAI

# Configure logging
current_dir = Path(__file__).resolve().parent
log_dir = current_dir.parents[2]
log_file_path = log_dir / 'log.txt'
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Qwen2AudioMM(BaseMM):
    def __init__(self):
        self.client = OpenAI(
            api_key='EMPTY',
            base_url='http://172.24.168.18:8000/v1',
        )
        self.audio_dir = '/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/server/test/'
        self.model_type = self.client.models.list().data[0].id
        logging.info("Qwen2AudioMM instance has been initialized.")

    async def post_audio(self, combined_audio: bytes, lang: str = "auto") -> str:
        start_time = time.time()
        loop = asyncio.get_event_loop()
        wav_path =  await loop.run_in_executor(None, self._convert_to_wav, combined_audio)
        # wav_path = self._convert_to_wav(combined_audio)
        elapsed_time = time.time() - start_time
        logging.info(f"储存为音频时间消耗： {elapsed_time:.4f} seconds")
        return wav_path  # Return WAV file path as string

    def _convert_to_wav(self, combined_audio: bytes) -> str:
        """
        将音频字节转换为WAV格式并保存到指定文件夹。
        """
        try:
            audio = AudioSegment.from_file(io.BytesIO(combined_audio))
            target_dir = "/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/qwen_speaker"
            os.makedirs(target_dir, exist_ok=True)
            # filename = f"{uuid.uuid4().hex}.wav"
            filename = "test.wav"
            file_path = os.path.join(target_dir, filename)
            audio.export(file_path, format="wav")
            logging.info(f'qwen_mm：保存采集到的人声到wav路径：{file_path}')
            return file_path
        except Exception as e:
            logging.error(f"qwen_mm：音频转换错误: {e}")
            raise

    async def post_text(self, wav_path, text_queue: asyncio.Queue, history_queue: asyncio.Queue, max_history_num=0):
        conversation = []
        try:
            start_time = time.time()
            with open(wav_path, 'rb') as f:
                aud_base64 = base64.b64encode(f.read()).decode('utf-8')
            audio_url = f'data:audio/wav;base64,{aud_base64}'

            new_messages = {
                'role': 'user',
                'content': [
                    {'type': 'audio_url', 'audio_url': {'url': audio_url}},
                ]
            }
            conversation.append(new_messages)

            stream_resp = self.client.chat.completions.create(model=self.model_type,messages=conversation,stream=True,temperature=0)
            result = ""
            first_few = 3  # Control logging for the first few responses
            count = 0
            for chunk in stream_resp:
                if not chunk:
                    continue
                content = chunk.choices[0].delta.content
                if content is not None:
                    result += content
                    count += 1
                    await text_queue.put(content)
                    if count <= first_few:
                        elapsed_time = time.time() - start_time
                        logging.info(f"self.client 返回值： {content}: {elapsed_time:.4f} seconds")
            conversation.append({"role": "assistant", "content": result})
            if max_history_num > 0:
                conversation = conversation[-max_history_num:]
            for msg in conversation:
                await history_queue.put(msg)

        except Exception as e:
            logging.error(f"Request failed: {e}")
            await text_queue.put(None)

    async def close(self):
        pass
