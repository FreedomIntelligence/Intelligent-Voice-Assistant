import asyncio
from silero_vad import load_silero_vad, get_speech_timestamps
import torch
import torchaudio
from enum import Enum
import time
import datetime
import os
import logging
import io
import uuid
import numpy as np
import soundfile as sf
from pathlib import Path
from collections import deque

logging.basicConfig(
    filename=Path('./log.txt'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DetectionState(Enum):
    BEFORE_SPEECH = 1
    DURING_SPEECH = 2
    AFTER_SPEECH = 3

class AudioDetectionModule:
    def __init__(self,
                 model, 
                 audio_queue: asyncio.Queue, 
                 detected_audio_queue: asyncio.Queue,
                 send_text_queue: asyncio.Queue,
                 history_audio_queue: asyncio.Queue,
                 reset_callback, 
                 orig_sample_rate=16000, 
                 target_sample_rate=16000, 
                 buffer_duration=1.0,
                 silence_duration=3.0,
                 history_maxlen=1):  # 新增参数，默认存储1个前置音频块
        """
        初始化语音检测模块。
        """
        self.model = model
        self.audio_queue = audio_queue
        self.detected_audio_queue = detected_audio_queue
        self.send_text_queue = send_text_queue
        self.history_audio_queue = history_audio_queue
        self.reset_callback = reset_callback
        self.orig_sample_rate = orig_sample_rate
        self.target_sample_rate = target_sample_rate
        self.buffer_size = int(target_sample_rate * buffer_duration)
        self.buffer = torch.tensor([], dtype=torch.float32)
        self.silence_duration = silence_duration
        self.state = DetectionState.BEFORE_SPEECH
        self.collected_audio = torch.tensor([], dtype=torch.float32)
        self.last_speech_time = None

        # 历史缓冲区：存储多个前置缓冲区
        self.history_buffers = deque(maxlen=history_maxlen)
        logging.info(f'历史缓冲区已设置，最多存储 {history_maxlen} 个前置缓冲区')

        # 如果原始采样率与目标采样率不同，初始化重采样器
        if self.orig_sample_rate != self.target_sample_rate:
            self.resampler = torchaudio.transforms.Resample(
                orig_freq=self.orig_sample_rate, 
                new_freq=self.target_sample_rate
            )
            logging.info('初始化重采样器')
        else:
            self.resampler = None
            logging.info('采样率匹配，无需重采样器')

        logging.info('Silero VAD 初始化完成')
        logging.info(f'初始状态: {self.state.name}')

    async def log(self, message: str):
        """
        发送日志消息到 send_text_queue。
        """
        if self.send_text_queue:
            await self.send_text_queue.put(message)
        logging.info(message)
        
    async def save_audio_async(self, audio_bytes: bytes, save_dir: str):
        """
        异步保存音频文件。

        :param audio_bytes: 要保存的音频字节数据
        :param save_dir: 保存目录
        """
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        save_path = f"{save_dir}/detected_speech_{timestamp}.wav"

        # 使用 asyncio.to_thread 异步执行保存操作
        try:
            async with asyncio.Lock():
                with open(save_path, 'wb') as f:
                    f.write(audio_bytes)
            save_log = f"已异步保存检测到的语音到文件: {save_path}"
            logging.info(save_log)
        except Exception as e:
            error_message = f"异步保存音频时出错: {e}"
            await self.log(error_message)

    async def _handle_after_speech(self):
        """
        处理进入 AFTER_SPEECH 状态后的操作。
        """
        try:
            await asyncio.sleep(self.silence_duration)
            self.buffer = torch.tensor([], dtype=torch.float32)
            logging.info("缓冲区已清空。")

            cleared = 0
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.task_done()
                    cleared += 1
                except:
                    break
            logging.info(f"清空 audio_queue，共清除 {cleared} 个音频块。")

            # Reset state to BEFORE_SPEECH
            self.state = DetectionState.BEFORE_SPEECH
            await self.log("进入状态1：说话前")

            # 清空历史缓冲区
            self.history_buffers.clear()
            logging.info("历史缓冲区已清空。")
        except Exception as e:
            await self.log(f"处理 AFTER_SPEECH 时出错: {e}")
            
    async def periodic_logger(self):
        """每隔60秒记录一次日志，表明 run 函数仍在运行。"""
        try:
            while True:
                logging.info("audio_detection run 函数正在正常运行。")
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass

    async def run(self):
        # 启动定期日志记录协程
        logger_task = asyncio.create_task(self.periodic_logger())
        logging.info('开始运行 AudioDetectionModule')
        await self.log(f'开始运行 AudioDetectionModule，初始状态: {self.state.name}')
        while True:
            try:
                audio_data = await self.audio_queue.get()
            except asyncio.TimeoutError:
                # 如果在一段时间内没有音频数据，继续循环
                continue

            logging.info(f'接收到音频数据，长度: {len(audio_data)}')
            sample_rate = self.orig_sample_rate

            # 处理16位PCM数据：转换为torch.Tensor并归一化
            if isinstance(audio_data, bytes):
                # 假设音频数据是bytes类型的16位PCM
                audio_array = np.frombuffer(audio_data, dtype=np.int16).copy()
                audio_tensor = torch.tensor(audio_array, dtype=torch.float32) / 32768.0     ## numpy 数组转换为 PyTorch 张量，并将其标准化为浮点数范围 [−1.0,1.0][−1.0,1.0]
            elif isinstance(audio_data, torch.Tensor):
                if audio_data.dtype == torch.int16:
                    audio_tensor = audio_data.float() / 32768.0  ## 转换为浮点数并标准化
                elif audio_data.dtype == torch.float32:
                    audio_tensor = audio_data
                else:
                    await self.log("不支持的Tensor数据类型，跳过当前音频块。")
                    self.audio_queue.task_done()
                    continue
            else:
                await self.log("audio_data格式不支持，跳过当前音频块。")
                self.audio_queue.task_done()
                continue

            if self.resampler:
                logging.info("音频块采样率不匹配，开始重采样。")
                try:
                    audio_tensor = self.resampler(audio_tensor)
                    logging.info("音频块重采样成功。")
                except Exception as e:
                    await self.log(f"重采样时出错: {e}")
                    self.audio_queue.task_done()
                    continue

            # 追加到缓冲区
            self.buffer = torch.cat((self.buffer, audio_tensor))
            logging.info(f"追加到缓冲区，当前缓冲区长度: {len(self.buffer)}")

            # 在这里不再更新历史缓冲区
            # self.history_buffers.append(audio_tensor.clone())
            # logging.debug(f"更新历史缓冲区，目前存储 {len(self.history_buffers)} 个前置音频块。")

            # 当缓冲区足够大时，进行 VAD
            if len(self.buffer) >= self.buffer_size:
                logging.info("缓冲区大小达到阈值，开始进行语音活动检测。")
                try:
                    speech_timestamps = get_speech_timestamps(
                        self.buffer, 
                        self.model, 
                        sampling_rate=self.target_sample_rate,
                        threshold=0.95  # 调整阈值以控制敏感度
                    )
                except Exception as e:
                    await self.log(f"VAD处理时出错: {e}")
                    self.audio_queue.task_done()
                    continue

                current_time = time.time()

                if speech_timestamps:
                    if self.state == DetectionState.BEFORE_SPEECH:
                        # Transition to DURING_SPEECH
                        self.state = DetectionState.DURING_SPEECH

                        # Call reset_callback before processing
                        try:
                            await self.reset_callback()
                            await self.send_text_queue.put('$clear$')
                            # await self.reset_callback()
                            logging.info(f"调用 reset_callback 成功")
                        except Exception as e:
                            await self.log(f"调用 reset_callback 时出错: {e}")

                        # 包含所有历史缓冲区
                        if len(self.history_buffers) > 0:
                            historical_audio = torch.cat(list(self.history_buffers))
                            self.collected_audio = torch.cat((historical_audio, self.buffer.clone()))
                            logging.debug("包含所有历史缓冲区到 collected_audio。")
                        else:
                            self.collected_audio = self.buffer.clone()
                            logging.debug("无历史缓冲区，仅包含当前缓冲区到 collected_audio。")
                        
                        self.last_speech_time = current_time
                        log_message = "你继续说，我在听..."
                        await self.log(log_message)
                    elif self.state == DetectionState.DURING_SPEECH:
                        self.collected_audio = torch.cat((self.collected_audio, self.buffer.clone()))
                        self.last_speech_time = current_time
                        log_message = "持续说话中..."
                        await self.log(log_message)
                else:
                    if self.state == DetectionState.DURING_SPEECH:
                        # Transition to AFTER_SPEECH
                        self.state = DetectionState.AFTER_SPEECH
                        self.collected_audio = torch.cat((self.collected_audio, self.buffer.clone()))
                        self.last_speech_time = current_time
                        log_message = "让我想想怎么回答..."
                        await self.send_text_queue.put(log_message)

                        audio_bytes_io = io.BytesIO()
                        # 转换为正确的形状（需要是 (num_samples, num_channels)）
                        audio_np = self.collected_audio.cpu().numpy()
                        if audio_np.ndim == 1:
                            audio_np = np.expand_dims(audio_np, axis=1)
                        sf.write(audio_bytes_io, audio_np, self.target_sample_rate, format='WAV')
                        audio_bytes = audio_bytes_io.getvalue()

                        await self.detected_audio_queue.put(audio_bytes)
                        logging.info("检测到完整语音片段，已放入 detected_audio_queue。")
                        await self.history_audio_queue.put(audio_bytes)
                        logging.info("检测到完整语音片段，已放入 history_audio_queue。")

                        # 异步保存音频文件
                        save_dir = "/home/sunzhu/Real-time-hyperpersonification/GPTo_V4/speaker_wav"
                        await self.save_audio_async(audio_bytes, save_dir)

                        # 直接在 run 方法中处理 AFTER_SPEECH，阻塞 run 函数
                        await self._handle_after_speech()

                # 在这里将当前缓冲区添加到历史缓冲区
                self.history_buffers.append(self.buffer.clone())
                logging.debug(f"更新历史缓冲区，目前存储 {len(self.history_buffers)} 个前置缓冲区。")

                # 重置缓冲区
                self.buffer = torch.tensor([], dtype=torch.float32)
                logging.info("缓冲区已重置。")

            self.audio_queue.task_done()
