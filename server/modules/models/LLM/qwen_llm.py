import asyncio
from typing import List, Dict, Any
from openai import OpenAI
from typing_extensions import TypedDict, NotRequired, Required
from models.LLM.base_llm import BaseLLM
import logging
from pathlib import Path

current_dir = Path(__file__).resolve().parent
log_dir = current_dir.parents[2]
log_file_path = log_dir / 'log.txt'
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class GenerateConfig(TypedDict):
    model: Required[str]
    temperature: NotRequired[float]
    top_p: NotRequired[float]
    max_tokens: Required[int]
    n: NotRequired[int]
    stop: Required[str]

generate_config: GenerateConfig = {
    "model": "qwen",
    "temperature": 0.8,
    "top_p": 0.8,
    "max_tokens": 3000,
    "stop": ['<|endoftext|>'],
}

class QwenLLM(BaseLLM):
    def construct_messages(self, system_prompt, query, history):
        messages = [{"role": "system", "content": system_prompt}]
        for i in history:
            messages.append(i)
        messages.append({"role": "user", "content": query})
        return messages

    def request_qwen(self, query, system_prompt, api_url="http://172.24.168.50:6100/v1", history=[]):
        client = OpenAI(
            api_key='none',
            base_url=api_url,
            max_retries=2
        )
        input_data = self.construct_messages(system_prompt, query, history)
        
        try:
            chat_response = client.chat.completions.create(
                messages=input_data,
                **generate_config
            )
            return chat_response.choices[0].message.content
        except Exception as e:
            return "<|wrong data|>"
    
    async def post_text(self, text: str, text_queue: asyncio.Queue, history_queue: asyncio.Queue):
        system_prompt = 'You are a helpful assistant.'
        logging.info('开始发送qwen llm请求...')
        response_text = self.request_qwen(text, system_prompt=system_prompt, history=[])
        logging.info(f'成功得到qwen llm请求结果：{response_text}')
        # 将响应文本按字符逐个放入队列中
        for char in response_text:
            await text_queue.put(char)
        
        # 放入结束标志
        await text_queue.put(None)

    async def close(self):
        pass

if __name__ == '__main__':
    async def main():
        text_queue = asyncio.Queue()
        qwen_llm = QwenLLM()
        
        async def consume_queue():
            count = 0
            while True:
                char = await text_queue.get()
                if char is None:
                    break
                count += 1
                print(f"第 {count} 个取出来的值为: {char}")
        
        await asyncio.gather(
            qwen_llm.post_text("Hello, Qwen!", text_queue),
            consume_queue()
        )

    asyncio.run(main())