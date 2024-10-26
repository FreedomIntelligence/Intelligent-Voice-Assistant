from abc import ABC, abstractmethod
import asyncio

class BaseMM(ABC):
    @abstractmethod
    async def post_audio(self, combined_audio: bytes, lang: str = "auto") -> str:
        pass

    @abstractmethod
    async def post_text(self, text: str, text_queue: asyncio.Queue, history_queue: asyncio.Queue):
        pass
    
    async def reset(self):
        pass