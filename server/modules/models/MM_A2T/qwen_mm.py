import asyncio
import aiohttp
import tempfile
import os
import uuid
import io
from typing import List, Optional, Dict
from pydub import AudioSegment
from models.MM_A2T.base_mm import BaseMM
import logging
from pathlib import Path

current_dir = Path(__file__).resolve().parent
log_dir = current_dir.parents[2]
log_file_path = log_dir / 'log.txt'
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class QwenMM(BaseMM):
    def __init__(self, session: aiohttp.ClientSession):
        """
        初始化 QwenMM 实例。
        """
        self.api_url = "http://172.24.168.8:8000/chat/"
        self.timeout = 60
        self.session = session

    async def post_audio(self, combined_audio: bytes, lang: str = "auto") -> str:
        """
        将接收到的音频字节转换为WAV格式并保存到指定文件夹中。
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._convert_to_wav, combined_audio)

    def _convert_to_wav(self, combined_audio: bytes) -> str:
        """
        将音频字节转换为WAV格式并保存到指定文件夹。
        """
        try:
            audio = AudioSegment.from_file(io.BytesIO(combined_audio))
            target_dir = "/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/gpto/qwen_speaker"
            os.makedirs(target_dir, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.wav"
            # filename = "test.wav"
            file_path = os.path.join(target_dir, filename)
            audio.export(file_path, format="wav")
            logging.info(f'qwen_mm：保存采集到的人声到wav路径：{file_path}')
            return file_path
        except Exception as e:
            logging.error(f"qwen_mm：音频转换错误: {e}")
            raise

    async def post_text(self, text: str, text_queue: asyncio.Queue, history_queue: asyncio.Queue, max_history_num=6):
        """
        使用WAV路径与模型进行通信，处理模型的响应并更新队列。

        :param text: WAV文件的路径。
        :param text_queue: 用于存储模型响应文本的异步队列。
        :param history_queue: 用于存储对话历史的异步队列，最多保留最新的6条记录。
        :param max_history_num: 历史记录的最大数量，默认为6。
        """
        history = []
        temp_storage = []

        # 从 history_queue 中取出所有历史记录
        while not history_queue.empty():
            try:
                item = history_queue.get_nowait()
                temp_storage.append(item)  # 存储到临时列表
                if isinstance(item, list):
                    history.extend(item)
                else:
                    history.append(item)
            except asyncio.QueueEmpty:
                break

        logging.info(f'qwen_mm：history加载完毕，当前历史记录数：{len(history)}')

        # 将历史记录重新放回 history_queue
        for item in temp_storage:
            await history_queue.put(item)

        # 仅保留最新的 max_history_num 条历史记录
        if len(history) > max_history_num:
            history = history[-max_history_num:]

        payload = {
            "wav_path": text,
            "history": history
        }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            logging.info(f'qwen_mm：开始向API发送请求...')
            async with self.session.post(self.api_url, json=payload, headers=headers, timeout=self.timeout) as response:
                if response.status != 200:
                    text_resp = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"HTTP错误: {response.status} - {text_resp}"
                    )

                data = await response.json()

                # 验证响应数据结构
                if "response" not in data or "history" not in data:
                    raise ValueError("响应数据格式不正确，缺少'response'或'history'字段。")

                response_text = data["response"]
                updated_history = data["history"]

                # 逐字符放入 text_queue
                for char in response_text:
                    await text_queue.put(char)

                # 将最新的历史记录放入 history_queue
                await history_queue.put(updated_history[-1])

                logging.info(f'qwen_mm：得到API返回值response_text：{response_text}')
                logging.info(f'qwen_mm：得到API返回值updated_history最后一条：{updated_history[-1]}')

        except asyncio.TimeoutError:
            logging.error("请求超时，请稍后重试。")
            raise
        except aiohttp.ClientResponseError as http_err:
            logging.error(f"HTTP错误发生: {http_err}")
            raise
        except aiohttp.ClientError as req_err:
            logging.error(f"请求错误发生: {req_err}")
            raise
        except ValueError as val_err:
            logging.error(f"响应解析错误: {val_err}")
            raise

    async def close(self):
        """
        关闭HTTP会话。
        """
        await self.session.close()


if __name__ == "__main__":
    import io

    async def main():
        qwen_mm = QwenMM()

        wav_file_path = "/mnt/pfs-guan-ssai/nlu/zhaojiale/3oa-text-voice-data-generate/fish-speech/tools/generated_audio.wav"

        # 读取 WAV 文件并转换为字节
        try:
            with open(wav_file_path, 'rb') as f:
                combined_audio = f.read()
        except FileNotFoundError:
            print(f"指定的 WAV 文件未找到: {wav_file_path}")
            return
        except Exception as e:
            print(f"读取 WAV 文件时发生错误: {e}")
            return

        # 初始化队列
        text_queue = asyncio.Queue()
        history_queue = asyncio.Queue()

        # 添加初始对话历史
        initial_history = [{
            'audio': f'<audio>{wav_file_path}</audio>',
            'response': '「中性」\n\n人山人海，<strong>形容</strong>的是一片热闹的场景，人多得像山一样，像海一样，[breath]挤得水泄不通，通常用来形容人多的地方，或者大规模的群众活动。你是不是遇到了啥人多得不得了的情况啊？'
        }]

        # 将每个历史条目单独放入队列
        for item in initial_history:
            await history_queue.put(item)

        try:
            # 处理音频
            wav_path = await qwen_mm.post_audio(combined_audio)
            print(f"WAV文件路径: {wav_path}")

            # 发送文本（WAV路径）到模型
            await qwen_mm.post_text(wav_path, text_queue, history_queue)

            # 读取模型响应
            response_text = ""
            while not text_queue.empty():
                char = await text_queue.get()
                response_text += char
            print("模型响应:", response_text)

            # 读取更新后的历史记录
            updated_history = []
            while not history_queue.empty():
                updated_history.append(await history_queue.get())
            print("更新后的历史记录:", updated_history)

        except Exception as e:
            print(f"与模型通信时发生错误: {e}")
        finally:
            await qwen_mm.close()
            # 清理临时WAV文件
            # if os.path.exists(wav_path):
            #     os.remove(wav_path)

    asyncio.run(main())
