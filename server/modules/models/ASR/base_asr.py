from abc import ABC, abstractmethod


class BaseASR(ABC):
    @abstractmethod
    async def post_audio(self, combined_audio: bytes, lang: str = "auto") -> str:
        pass

    async def close(self):
        pass