import asyncio
import logging
from pathlib import Path

logging.basicConfig(
    filename=Path('./log.txt'),
    level=logging.INFO,  # 可以在开发时设置为 DEBUG，生产时设置为 INFO
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DataTransmissionModule:
    def __init__(self, send_audio_queue: asyncio.Queue, send_text_queue: asyncio.Queue,
                 history_audio_queue: asyncio.Queue, history_text_queue: asyncio.Queue):
        self.send_audio_queue = send_audio_queue
        self.send_text_queue = send_text_queue
        self.history_audio_queue = history_audio_queue
        self.history_text_queue = history_text_queue
        self.websocket = None

        self.audio_task: asyncio.Task = None
        self.text_task: asyncio.Task = None
        self.logger_task: asyncio.Task = None

        self.websocket_lock = asyncio.Lock()

    async def periodic_logger(self):
        """每60秒记录一次日志，指示run函数仍在正常运行。"""
        try:
            while True:
                logging.debug("data_transmission run 函数正在正常运行。")
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logging.debug("periodic_logger 任务被取消。")
            pass

    async def run(self):
        """启动周期性日志记录和发送任务。"""
        self.logger_task = asyncio.create_task(self.periodic_logger())

        self.audio_task = asyncio.create_task(self._send_audio())
        self.text_task = asyncio.create_task(self._send_text())

        await asyncio.gather(
            self.logger_task,
            self.audio_task,
            self.text_task,
            return_exceptions=True
        )

    async def _send_audio(self):
        logging.info("开始运行 _send_audio")
        audio_cache = []

        try:
            while True:
                audio_chunk = await self.send_audio_queue.get()
                logging.debug("从队列中获取到音频消息")

                if audio_chunk is not None:
                    # 添加音频块到缓存
                    audio_cache.append(audio_chunk)

                    async with self.websocket_lock:
                        if self.websocket:
                            try:
                                await self.websocket.send_bytes(audio_chunk)
                                logging.debug(f'成功发送音频，音频长度：{len(audio_chunk)}字节')
                            except Exception as e:
                                logging.error(f"WebSocket 发送音频错误: {e}")
                else:
                    if audio_cache:
                        merged_audio = b''.join(audio_cache)

                        try:
                            await self.history_audio_queue.put(merged_audio)
                            logging.debug(f"将合并后的音频存储到 history_audio_queue，长度：{len(merged_audio)}字节")
                        except Exception as e:
                            logging.error(f"存储合并后的音频到 history_audio_queue 错误: {e}")

                        audio_cache.clear()
                    else:
                        logging.debug("收到 None，但缓存为空，无需处理")

                self.send_audio_queue.task_done()

        except asyncio.CancelledError:
            logging.info("_send_audio 任务被取消")
            pass
        except Exception as e:
            logging.error(f"_send_audio 遇到异常: {e}")

    async def _send_text(self):
        logging.info("开始运行 _send_text")
        text_cache = []

        try:
            while True:
                text_message = await self.send_text_queue.get()
                logging.debug(f"从队列中获取到文本消息: {text_message}")

                if text_message is not None:
                    text_cache.append(text_message)

                    async with self.websocket_lock:
                        if self.websocket:
                            try:
                                await self.websocket.send_text(text_message)
                                logging.debug(f'成功发送文本：{text_message}')
                            except Exception as e:
                                logging.error(f"WebSocket 发送文本错误: {e}")
                else:
                    if text_cache:
                        merged_text = ''.join(text_cache)
                        await self.history_text_queue.put(merged_text)
                        logging.debug(f"已将合并后的文本存储到 history_text_queue: {merged_text}")
                        text_cache.clear()
                    else:
                        logging.debug("缓存为空，无需合并和存储。")

                self.send_text_queue.task_done()

        except asyncio.CancelledError:
            logging.info("_send_text 任务被取消")
            pass
        except Exception as e:
            logging.error(f"_send_text 遇到异常: {e}")

    async def set_websocket(self, websocket):
        """
        设置新的 WebSocket 连接。
        立即取消任何正在进行的发送任务，并使用新的 WebSocket 重新启动它们。
        """
        async with self.websocket_lock:
            self.websocket = websocket
            # logging.info("WebSocket 已更新。")

        # 取消旧的发送任务
        if self.audio_task and not self.audio_task.done():
            self.audio_task.cancel()
            try:
                await self.audio_task
            except asyncio.CancelledError:
                logging.info("_send_audio 任务已成功取消。")

        if self.text_task and not self.text_task.done():
            logging.info("正在取消 _send_text 任务。")
            self.text_task.cancel()
            try:
                await self.text_task
            except asyncio.CancelledError:
                logging.info("_send_text 任务已成功取消。")
        
        # 清空发送队列
        await self._clear_queue(self.send_audio_queue, "send_audio_queue")
        await self._clear_queue(self.send_text_queue, "send_text_queue")

        # 重新启动发送任务
        self.audio_task = asyncio.create_task(self._send_audio())
        self.text_task = asyncio.create_task(self._send_text())
        logging.info("已重新启动 _send_audio 和 _send_text 任务。")

    async def _clear_queue(self, queue: asyncio.Queue, queue_name: str):
        """清空指定的队列。"""
        try:
            while not queue.empty():
                removed = queue.get_nowait()
                queue.task_done()
            logging.info(f"{queue_name} 已被清空。")
        except Exception as e:
            logging.error(f"清空 {queue_name} 时遇到错误: {e}")
