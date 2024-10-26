from abc import ABC, abstractmethod
import asyncio


class BaseLLM(ABC):
    @abstractmethod
    async def post_text(self, text: str, text_queue: asyncio.Queue, history_queue: asyncio.Queue):
        pass

    async def close(self):
        pass