import asyncio
import aiohttp
import logging
from pathlib import Path
import aiofiles
from models.TTS.fish_speech_tts import FishSpeechTTS

logging.basicConfig(
    filename=Path('./log.txt'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TTSModule:
    def __init__(self, tts_queue: asyncio.Queue, send_audio_queue: asyncio.Queue):
        self.tts_queue = tts_queue
        self.send_audio_queue = send_audio_queue
        self._sample_rate = 16000
        self._sample_width = 2
        self._channels = 1
        self._cache_duration_seconds = 1
        self.tts_engine = FishSpeechTTS()
        self.tasks = set()
        self.reset_lock = asyncio.Lock()
        self.cache = bytearray()  # 添加全局缓存属性

    async def periodic_logger(self):
        """每隔60秒记录一次日志，表明 run 函数仍在运行。"""
        try:
            while True:
                logging.info("tts_module run 函数正在正常运行。")
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logging.info("periodic_logger 任务被取消")
            pass

    async def run(self, streaming: bool = False):
        """主 TTS 处理循环，支持流式和非流式选项。"""
        logging.info("tts_module 开始运行")
        # 启动定期日志记录协程
        logger_task = asyncio.create_task(self.periodic_logger())
        self.tasks.add(logger_task)
        logger_task.add_done_callback(self.tasks.discard)
        try:
            while True:
                text = await self.tts_queue.get()
                logging.info("tts_module 成功拿到一条文本")

                file_name = "/xxxx/generate.wav" ## 保存TTS合成后的语音片段

                try:
                    if streaming:
                        await self.process_audio_stream(text, file_name)
                    else:
                        await self.process_audio(text, file_name)
                    logging.info(f'成功合成一条音频：{text}')
                except Exception as e:
                    logging.error(f'处理文本 "{text}" 时发生错误: {e}')

                self.tts_queue.task_done()
        except asyncio.CancelledError:
            logging.info("run 任务被取消")
            raise
        except Exception as e:
            logging.error(f'运行过程中发生错误: {e}')
        finally:
            # 确保 logger_task 被取消
            logger_task.cancel()
            await logger_task

    async def process_audio_stream(self, text: str, file_path: Path):
        """Streams audio data directly to the send_audio_queue without using a cache."""
        try:
            async for data in self.tts_engine.stream(text):
                await self.send_audio_queue.put(data)
                logging.info('成功流式put音频')
        except asyncio.CancelledError:
            logging.info("process_audio_stream 被取消")
            raise
        except Exception as e:
            logging.error(f'流式处理音频时发生错误: {e}')

    async def process_audio(self, text: str, file_path):
        """积累并在流完成后处理音频数据。"""
        try:
            async for data in self.tts_engine.stream(text):
                self.cache.extend(data)

        except asyncio.CancelledError:
            logging.info("process_audio 被取消")
            raise
        finally:
            if self.cache:
                await self.send_audio_queue.put(bytes(self.cache))
                self.cache.clear()  # 确保最终缓存被清空

    async def reset(self):
        """
        快速重置模块，通过取消所有相关任务并重置 TTS 引擎。
        """
        async with self.reset_lock:
            logging.info("开始重置 TTSModule")
            
            # 取消所有任务（除了 run 方法自身）
            tasks = list(self.tasks)
            for task in tasks:
                task.cancel()
            
            # 等待所有任务取消完成
            await asyncio.gather(*tasks, return_exceptions=True)
            self.tasks.clear()
            
            # 清空全局缓存
            self.cache.clear()
            logging.info("全局缓存已清空")
            
            # 重新初始化 TTS 引擎（如果需要）
            # self.tts_engine = FishSpeechTTS()
            
            logging.info("TTSModule 重置完成")
