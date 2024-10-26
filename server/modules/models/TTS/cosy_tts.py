import asyncio
import aiohttp
import time
import subprocess
import sys
from typing import AsyncGenerator
from models.TTS.base_tts import BaseTTS
import logging
from pathlib import Path

# 设置日志路径
current_dir = Path(__file__).resolve().parent
log_dir = current_dir.parents[2]
log_file_path = log_dir / 'log.txt'
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class CosyTTS(BaseTTS):
    emo_inst_dict = {
        "「中性」": "David, is a mature man with a deep and magnetic voice.",
        "「快乐」": "David, is a mature man with a deep and magnetic voice. Now he is happy.",
        "「悲伤」": "David, is a mature man with a deep and magnetic voice. Now he is sad and painful.",
        "「惊讶」": "David, is a mature man with a deep and magnetic voice. Now he is surprised and unbelievable.",
        "「恐惧」": "David, is a mature man with a deep and magnetic voice. Now he is fearful.",
        "「厌恶」": "David, is a mature man with a deep and magnetic voice. Now he is disgusted and hated.",
        "「愤怒」": "David, is a mature man with a deep and magnetic voice. Now he is very fiery and angry.",
    }

    emo_tags = list(emo_inst_dict.keys())
    default_emo_tag = "「中性」"

    def __init__(self, 
                 spk_id: str = "中文男", 
                 api_url: str = "http://172.24.162.115:50001/inference_instruct"):
        """
        初始化 CosyTTS 实例。

        :param spk_id: 说话人 ID
        :param api_url: TTS 服务的 API URL
        """
        self.spk_id = spk_id
        self.api_url = api_url
        self.session = aiohttp.ClientSession()
        self.current_emo_tag = self.default_emo_tag  # 初始化当前情感标签为默认值

    async def stream(self, text: str) -> AsyncGenerator[bytes, None]:
        emo_tag, tts_text = self._parse_text(text)

        form_data = {
            'tts_text': tts_text,
            'spk_id': self.spk_id,
            'instruct_text': self.emo_inst_dict.get(emo_tag, self.emo_inst_dict[self.default_emo_tag])
        }

        try:
            logging.info(f"发送 POST 请求到 {self.api_url}")
            async with self.session.post(self.api_url, data=form_data) as response:
                logging.info(f"收到响应状态码: {response.status}")
                if response.status != 200:
                    error_text = await response.text()
                    logging.error(f"请求失败，状态码: {response.status}, 响应: {error_text}")
                    return

                # 收集所有PCM数据
                pcm_data = bytearray()
                async for chunk in response.content.iter_chunked(1024):
                    if chunk:
                        logging.debug("收到TTS返回的音频块")
                        pcm_data.extend(chunk)

                logging.info("所有PCM数据已接收，开始转换为WAV格式")

                # 使用FFmpeg将PCM转换为WAV
                process = await asyncio.create_subprocess_exec(
                    'ffmpeg',
                    '-f', 's16le',        # 输入格式
                    '-ar', '22050',       # 采样率
                    '-ac', '1',           # 声道数
                    '-i', 'pipe:0',       # 输入来自stdin
                    '-f', 'wav',          # 输出格式
                    'pipe:1',             # 输出到stdout
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # 发送PCM数据到FFmpeg的stdin并获取WAV数据
                stdout, stderr = await process.communicate(input=pcm_data)

                if process.returncode != 0:
                    error_message = stderr.decode()
                    logging.error(f"FFmpeg转换失败: {error_message}")
                    return

                logging.info("PCM数据已成功转换为WAV格式，开始流式传输WAV数据")

                # 以块的形式返回WAV数据
                chunk_size = 1024
                for i in range(0, len(stdout), chunk_size):
                    yield stdout[i:i + chunk_size]

        except aiohttp.ClientError as e:
            logging.error(f"发送 POST 请求到 {self.api_url} 时发生错误: {e}")
        except Exception as ex:
            logging.error(f"发生未预期的错误: {ex}")

    def _parse_text(self, text: str):
        """
        解析输入文本，提取情感标签和实际 TTS 文本。

        :param text: 输入文本
        :return: (emo_tag, tts_text)
        """
        for tag in self.emo_tags:
            if text.startswith(tag):
                self.current_emo_tag = tag  # 更新当前情感标签
                return tag, text[len(tag):].strip()
        # 如果没有匹配的情感标签，使用当前的情感标签
        return self.current_emo_tag, text.strip()

    async def close(self):
        """
        关闭 aiohttp 会话以释放资源。
        """
        await self.session.close()

if __name__ == "__main__":
    async def main():
        cosy_tts = CosyTTS()
        try:
            texts = [
                "「快乐」今天是个好天气。",
                "明天也会是好天气。",
                "「悲伤」我感到有些难过。",
                "继续保持积极的心态。",
                "「愤怒」这真的让我生气！",
                "希望问题能尽快解决。"
            ]

            for text in texts:
                print(f"处理文本: {text}")
                async for chunk in cosy_tts.stream(text):
                    print(f"收到音频块大小: {len(chunk)} bytes")
                print("-" * 40)

        finally:
            await cosy_tts.close()
    asyncio.run(main())
