import ormsgpack
import aiohttp
from models.TTS.base_tts import BaseTTS
from pydantic import BaseModel, Field, conint
from typing import Annotated, Literal, Optional, List
from pathlib import Path
import logging

current_dir = Path(__file__).resolve().parent
log_dir = current_dir.parents[2]
log_file_path = log_dir / 'log.txt'
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ServeReferenceAudio(BaseModel):
    audio: str
    text: str

class ServeTTSRequest(BaseModel):
    text: str
    chunk_length: Annotated[int, conint(ge=100, le=300, strict=True)] = 200
    format: Literal["wav", "pcm", "mp3"] = "wav"
    mp3_bitrate: Literal[64, 128, 192] = 128
    references: List[ServeReferenceAudio] = []
    reference_id: Optional[str] = None
    normalize: bool = True
    opus_bitrate: Optional[int] = 64
    latency: Literal["normal", "balanced"] = "normal"
    streaming: bool = False
    emotion: Optional[str] = None
    max_new_tokens: int = 1024
    top_p: Annotated[float, Field(ge=0.1, le=1.0, strict=True)] = 0.7
    repetition_penalty: Annotated[float, Field(ge=0.9, le=2.0, strict=True)] = 1.2
    temperature: Annotated[float, Field(ge=0.1, le=1.0, strict=True)] = 0.7

class FishSpeechTTS(BaseTTS):
    def __init__(
        self,
        url: str = 'http://10.27.127.33:8085/v1/tts',
        api_key: str = 'YOUR_API_KEY',  # 固定 API Key
        output_format: str = "wav",
        chunk_length: int = 200,
        mp3_bitrate: int = 64,
        opus_bitrate: int = -1000,
        latency: str = "normal",
        streaming: bool = True,
        normalize: bool = True,
        top_p: float = 0.7,
        repetition_penalty: float = 1.2,
        temperature: float = 0.7,
    ):
        self.url = url
        self.api_key = api_key
        self.output_format = output_format
        self.chunk_length = chunk_length
        self.mp3_bitrate = mp3_bitrate
        self.opus_bitrate = opus_bitrate
        self.latency = latency
        self.streaming = streaming
        self.normalize = normalize
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty
        self.temperature = temperature
        self.session = aiohttp.ClientSession()
    
    async def stream(self, text: str, references: Optional[List[ServeReferenceAudio]] = None):
        """Stream audio data using FishSpeech."""
        if references is None:
            references = []

        reference_audio = ["/home/sunzhu/Real-time-hyperpersonification/GPTo_V4/server/modules/models/TTS/demo2.mp3"]
        reference_text = ["从前，在一个宁静的小村庄里，有一个年轻的女孩名叫艾莉。她对星星充满了好奇，总是喜欢在夜晚仰望星空。有一天晚上，艾莉发现了一颗与众不同的星星，它闪烁着奇异的光芒，仿佛在向她传递什么信息。艾莉心中充满了好奇，决定一探究竟。她带上了望远镜，徒步穿越森林来到了一座小山顶。这里是观星的绝佳地点。夜幕降临，艾莉用望远镜仔细观察那颗特别的星星。"]
        references = [
            ServeReferenceAudio(audio=ref_audio, text=ref_text)
            for ref_text, ref_audio in zip(reference_text, reference_audio)
        ]

        request_data = ServeTTSRequest(
            text=text,
            references=references,
            format=self.output_format,
            chunk_length=self.chunk_length,
            mp3_bitrate=self.mp3_bitrate,
            opus_bitrate=self.opus_bitrate,
            latency=self.latency,
            streaming=self.streaming,
            normalize=self.normalize,
            top_p=self.top_p,
            repetition_penalty=self.repetition_penalty,
            temperature=self.temperature,
        )
        
        packed_data = ormsgpack.packb(request_data.dict(), option=ormsgpack.OPT_SERIALIZE_PYDANTIC)
        
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/msgpack",
        }
        logging.info(f"开始准备向fishAPI发送请求")
        try:
            async with self.session.post(self.url, data=packed_data, headers=headers) as response:
                if response.status != 200:
                    error = await response.json()
                    logging.error(f"请求失败: {error}")
                    raise Exception(f"Request failed with status {response.status}: {error}")
                
                num = 0
                async for chunk in response.content.iter_chunked(1024):
                    if chunk:
                        yield chunk
                    if num < 2:
                        num = num + 1
                        logging.info(f"已收到第{str(num)}块音频")
        
        except Exception as e:
            logging.error(f"请求失败: {e}")
            raise
    
    async def close(self):
        pass
