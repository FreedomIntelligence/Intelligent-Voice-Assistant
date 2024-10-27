import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from modules.audio_detection import AudioDetectionModule
from modules.audio_processing import AudioProcessingModule
from modules.text_processing import TextProcessingModule
from modules.tts_module import TTSModule
from modules.data_transmission import DataTransmissionModule
from modules.data_storage import DataStorageModule
from silero_vad import load_silero_vad
from fastapi.middleware.cors import CORSMiddleware
import aiofiles

app = FastAPI()

# 添加 CORS 中间件（可选，根据需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 根据实际情况调整
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Pipeline:
    def __init__(self):
        # 定义各个队列
        self.raw_audio_queue = asyncio.Queue()
        self.detected_audio_queue = asyncio.Queue()
        self.text_queue = asyncio.Queue()
        self.send_text_queue = asyncio.Queue()
        self.tts_queue = asyncio.Queue()
        self.send_audio_queue = asyncio.Queue()
        self.history_text_queue = asyncio.Queue()
        self.history_audio_queue = asyncio.Queue()

        self.model = None  # 延迟加载 silero_vad

        # 初始化模块引用为 None
        self.audio_detection = None
        self.audio_processing = None
        self.text_processing = None
        self.tts_module = None
        self.data_transmission = None

        self.tasks = []
        self.websocket = None

    async def initialize_pipeline(self, websocket: WebSocket):
        self.websocket = websocket
        self.data_transmission = DataTransmissionModule(
            send_audio_queue=self.send_audio_queue,
            send_text_queue=self.send_text_queue,
            history_audio_queue=self.history_audio_queue,
            history_text_queue=self.history_text_queue,
        )
        self.data_transmission.set_websocket(websocket)

        # 初始化各个模块并发送状态更新
        await self.send_status("Modules initializing.")
        # await self.send_status("Initializing silero_vad model...")
        self.model = load_silero_vad()

        self.audio_detection = AudioDetectionModule(
            model=self.model,
            audio_queue=self.raw_audio_queue,
            detected_audio_queue=self.detected_audio_queue,
            send_text_queue=self.send_text_queue,
            history_audio_queue=self.history_audio_queue,
            reset_callback=self.reset_pipeline,
        )
        
        self.audio_processing = AudioProcessingModule(
            audio_queue=self.detected_audio_queue,
            text_queue=self.text_queue,
            history_audio_queue=self.history_audio_queue,
            history_text_queue=self.history_text_queue,
            send_text_queue=self.send_text_queue,
        )
        
        self.text_processing = TextProcessingModule(
            text_queue=self.text_queue,
            tts_queue=self.tts_queue,
            send_text_queue=self.send_text_queue,
        )
        
        self.tts_module = TTSModule(
            tts_queue=self.tts_queue,
            send_audio_queue=self.send_audio_queue,
        )

        # 启动任务
        self.tasks = [
            asyncio.create_task(self.audio_detection.run()),
            asyncio.create_task(self.audio_processing.run()),
            asyncio.create_task(self.text_processing.run()),
            asyncio.create_task(self.tts_module.run()),
            asyncio.create_task(self.data_transmission.run())
        ]
        await self.send_status("All modules initialized and tasks started.")

    async def send_status(self, message: str):
        if self.websocket:
            await self.websocket.send_text(message)

    async def reset_pipeline(self):
        print("Resetting pipeline...")
        # 清空除上下文队列之外的所有队列
        await self.clear_queues()
        # 释放资源（api请求）
        if self.text_processing:
            self.text_processing.reset()
        if self.audio_processing:
            await self.audio_processing.reset()
        if self.tts_module:
            await self.tts_module.reset()
        if self.data_transmission:
            await self.data_transmission.set_websocket(self.websocket)

    async def clear_queues(self):
        queues = [
            self.raw_audio_queue,
            self.detected_audio_queue,
            self.text_queue,
            self.tts_queue,
            self.send_audio_queue
        ]
        for q in queues:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except asyncio.QueueEmpty:
                    break

    async def clear_history_queues(self):
        queues = [
            self.history_text_queue,
            self.history_audio_queue
        ]
        for q in queues:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except asyncio.QueueEmpty:
                    break

    async def shutdown(self):
        await self.reset_pipeline()
        await self.clear_history_queues()
        for task in self.tasks:
            task.cancel()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pipeline = Pipeline()
    
    # 初始化 pipeline 并发送状态更新
    await pipeline.initialize_pipeline(websocket)
    
    # 发送欢迎消息
    await pipeline.send_text_queue.put('Welcome to the GPTo server!')
    
    try:
        while True:
            data = await websocket.receive_bytes()          # 接收客户端发送的数据
            await pipeline.raw_audio_queue.put(data)
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await pipeline.shutdown()
