from models.MM_A2T.base_mm import BaseMM
import asyncio
import aiohttp
import os
from typing import Optional
from datetime import datetime


class VITAMM(BaseMM):
    def __init__(self):
        self.api_url = 'http://172.24.168.66:8000/infer'
        self.audio_dir = "/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/speaker_wav"
        os.makedirs(self.audio_dir, exist_ok=True)

    async def post_audio(self, combined_audio: bytes, lang: str = "auto") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}.wav"
        file_path = os.path.join(self.audio_dir, filename)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._write_file, file_path, combined_audio)
        
        return file_path

    def _write_file(self, file_path: str, data: bytes):
        with open(file_path, 'wb') as f:
            f.write(data)

    async def post_text(self, audio_path: str, text_queue: asyncio.Queue, history_queue: asyncio.Queue):
        async with aiohttp.ClientSession() as session:
            data = {
                "text": None,
                "audio": audio_path,
                "image": None,
                "video": None
            }

            try:
                async with session.post(self.api_url, json=data) as response:
                    if response.status == 200:
                        async for line in response.content:
                            decoded_line = line.decode('utf-8').strip()
                            if decoded_line:
                                await text_queue.put(decoded_line)
                    else:
                        error_text = f"请求失败，状态码: {response.status}"
                        print(error_text)
            except aiohttp.ClientError as e:
                error_text = f"请求异常: {e}"
                print(error_text)

    async def reset(self):
        # 目前不需要实现
        pass


if __name__ == "__main__":
    async def main():
        vitam = VITAMM()
        
        audio_file_path = "/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/speaker_wav/detected_speech_20241022_163717.wav"
        # with open(audio_file_path, 'rb') as f:
        #     audio_bytes = f.read()
        # wav_path = await vitam.post_audio(audio_bytes)
        # print(f"音频已保存至: {wav_path}")
        
        
        text_queue = asyncio.Queue()
        history_queue = asyncio.Queue()
        await vitam.post_text(str(audio_file_path), text_queue, history_queue)


        while not text_queue.empty():
            content = await text_queue.get()
            print(f"队列内容: {content}")

    asyncio.run(main())
