import edge_tts
from TTS.base_tts import BaseTTS
import asyncio

class EdgeTTS(BaseTTS):
    def __init__(self, voice: str = "zh-CN-YunxiNeural"):
        self.voice = voice
        self.communicate = None

    async def stream(self, text: str):
        """Stream audio data using edge_tts."""
        self.communicate = edge_tts.Communicate(text, self.voice)
        async for chunk in self.communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    async def close(self):
        """Close the Communicate session if necessary."""
        if self.communicate:
            await self.communicate.close()
