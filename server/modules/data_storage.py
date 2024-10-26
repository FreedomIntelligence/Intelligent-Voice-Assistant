import asyncio
import logging
from pathlib import Path

logging.basicConfig(
    filename=Path('./log.txt'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DataStorageModule:
    def __init__(self, history_text_queue: asyncio.Queue, history_audio_queue: asyncio.Queue):
        self.history_text_queue = history_text_queue
        self.history_audio_queue = history_audio_queue


        
    