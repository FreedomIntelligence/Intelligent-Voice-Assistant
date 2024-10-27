import aiohttp
import json
from models.LLM.base_llm import BaseLLM
import asyncio
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

class DeepSeekLLM(BaseLLM):
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.api_key = ""
        self.base_url = "XXXX"

    async def post_text(self, text: str, text_queue: asyncio.Queue, history_queue: asyncio.Queue, max_history: int = 0):
        """
        发送文本到DeepSeek LLM API并将生成的文本块加入队列。
        支持多轮对话，通过history_queue维护对话历史。

        参数:
            text (str): 用户输入的文本。
            text_queue (asyncio.Queue): 用于存储LLM回复的队列。
            history_queue (asyncio.Queue): 用于存储对话历史的队列。
            max_history (int): 最大使用的历史对话轮数。
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 构建消息列表，包括历史对话
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        
        # 提取并维护history_queue的原始状态
        temp_history = []
        while not history_queue.empty():
            msg = await history_queue.get()
            temp_history.append(msg)
        
        # 重新放回history_queue
        for msg in temp_history:
            await history_queue.put(msg)
        
        # 计算实际使用的历史轮数（每轮包括用户和助手的消息）
        actual_history = temp_history[-2 * max_history:]  # 每轮两条消息
        
        # 添加历史消息到messages列表
        for i, msg in enumerate(actual_history):
            role = "user" if i % 2 == 0 else "assistant"
            messages.append({"role": role, "content": msg})
        
        # 添加当前用户的消息
        messages.append({"role": "user", "content": text})

        payload = {
            "model": "lg-people-hospital",
            "messages": messages,
            "stream": True
        }

        try:
            logging.info("开始请求LLM")
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    logging.info("LLM 请求成功")
                    response_text = ""
                    async for line in resp.content:
                        line_decoded = line.decode('utf-8').strip()

                        if line_decoded == "data: [DONE]":
                            logging.info("收到所有LLM回复文本")
                            break

                        if line_decoded.startswith("data: "):
                            json_data = line_decoded[6:]
                            try:
                                json_resp = json.loads(json_data)
                                choices = json_resp.get("choices", [])
                                for choice in choices:
                                    if content := choice.get("delta", {}).get("content"):
                                        chunk = content.strip()
                                        if chunk:
                                            response_text += chunk
                                            await text_queue.put(chunk)
                                            logging.info(f"LLM 回复文本: {chunk}")
                            except json.JSONDecodeError as parse_exception:
                                logging.error(f"SSE 解析错误: {parse_exception}")
                    
                    # 将用户输入和LLM回复加入history_queue
                    await history_queue.put(text)
                    await history_queue.put(response_text)
                else:
                    error_text = await resp.text()
                    raise Exception(f"DeepSeek LLM API 错误 {resp.status}: {error_text}")
        except Exception as e:
            logging.error(f"DeepSeekLLM.post_text 错误: {e}")

    async def reset(self):
        pass


if __name__ == '__main__':
    async def main():
        async with aiohttp.ClientSession() as session:
            llm = DeepSeekLLM(session)
            text_queue = asyncio.Queue()
            history_queue = asyncio.Queue()

            user_inputs = [
                "你好，LLM！",
                "给我说个数字",
                "抱歉没听清，重复一下",
            ]

            for user_input in user_inputs:
                await llm.post_text(user_input, text_queue, history_queue, max_history=5)
                # 处理 LLM 的回复
                response = ""
                while not text_queue.empty():
                    chunk = await text_queue.get()
                    response += chunk
                print(f"用户: {user_input}")
                print(f"LLM: {response}")

            await llm.close()

    asyncio.run(main())
