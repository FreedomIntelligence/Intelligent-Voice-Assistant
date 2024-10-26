import asyncio
import logging
from pathlib import Path
import re  # 引入正则表达式模块

logging.basicConfig(
    filename=Path('./log.txt'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TextProcessingModule:
    def __init__(
        self, 
        text_queue: asyncio.Queue, 
        tts_queue: asyncio.Queue, 
        send_text_queue: asyncio.Queue, 
        ban_list=None  # 添加ban_list作为可选参数
    ):
        """
        初始化TextProcessingModule。
        :param text_queue: 从中消费文本的队列。
        :param tts_queue: 处理后的文本放入的队列。
        :param send_text_queue: 发送文本放入的队列。
        :param termination_timeout: 等待新文本的超时时间（秒）。
        :param ban_list: 要从文本中移除的字符或字符串列表。
        """
        self.text_queue = text_queue
        self.tts_queue = tts_queue
        self.send_text_queue = send_text_queue
        self.initial_termination_chars = ['.', '!', '?', '，', '。', '！', '~', '？', '；', ';', ',']
        self.subsequent_termination_chars = ['.', '!', '?', '。', '！', '~', '？', '；', ';']
        self.use_initial_chars = True
        self.current_text = []
        self.ban_list = ban_list or ["<strong>", "</strong>", "[laughter]", "[breath]", "「中性」","「快乐」","「悲伤」","「惊讶」","「恐惧」","「厌恶」","「愤怒」"]

        # 预编译ban_list的正则模式以提高性能
        if self.ban_list:
            # 转义每个禁止项以处理任何特殊的正则字符
            escaped_terms = [re.escape(term) for term in self.ban_list]
            # 使用单词边界确保只匹配完整的单词（可选）
            # 如果不需要单词边界，可以移除 r'\b' 和 r'\b'
            pattern = r'(' + '|'.join(escaped_terms) + r')'
            self.ban_pattern = re.compile(pattern, re.IGNORECASE)  # 添加不区分大小写的标志
        else:
            self.ban_pattern = None
            
    async def periodic_logger(self):
        """每隔5秒记录一次日志，表明 run 函数仍在运行。"""
        try:
            while True:
                logging.info("text_processing run 函数正在正常运行。")
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            # 处理任务取消时的清理工作（如果需要）
            pass

    async def run(self):
        """
        持续处理来自text_queue的文本。
        在开始一个新批次时使用初始终止字符，
        然后切换到后续的终止字符，直到队列空闲。
        处理文本中存在的终止字符时，进行适当的拆分。
        """
        # 启动定期日志记录协程
        logger_task = asyncio.create_task(self.periodic_logger())
        while True:
            try:
                # text = await self.text_queue.get()
                text = await asyncio.wait_for(self.text_queue.get(), timeout=2)
                
                self.current_text.append(text)
                logging.info(f'接收到文本：{text}')

                while True:
                    merged_text = ''.join(self.current_text)
                    
                    # 应用禁止词汇替换（在合并后进行）
                    if self.ban_pattern:
                        original_merged_text = merged_text
                        merged_text = self.ban_pattern.sub('', merged_text)
                        # if original_merged_text != merged_text:
                            # logging.info(f'文本中发现禁止词汇，已替换: 原文="{original_merged_text}"，处理后="{merged_text}"')

                    # 根据当前状态选择终止字符
                    termination_chars = self.initial_termination_chars if self.use_initial_chars else self.subsequent_termination_chars

                    # 查找任一终止字符的最早出现位置
                    termination_index = self.find_first_termination_char(merged_text, termination_chars)

                    if termination_index != -1:
                        # 在终止字符处分割文本
                        split_point = termination_index + 1  # 包含终止字符
                        before_termination = merged_text[:split_point]
                        after_termination = merged_text[split_point:]

                        # 将终止前的部分添加到current_text
                        self.current_text = [after_termination]  # 保留剩余部分

                        # 处理before_termination
                        await self.tts_queue.put(before_termination)
                        await self.send_text_queue.put('我的文本回复：' + before_termination)
                        logging.info(f'成功切割一条数据：{before_termination}')

                        # 如果是一个批次的第一次终止，切换终止字符
                        if self.use_initial_chars:
                            self.use_initial_chars = False
                    else:
                        # 未找到终止字符，等待更多文本
                        break

                self.text_queue.task_done()
            
            except asyncio.TimeoutError:
                # 达到超时，表示队列空闲
                if self.current_text:
                    # 合并并处理剩余的文本
                    merged_text = ''.join(self.current_text)
                    
                    # 再次应用禁止词汇替换（以确保完整的禁止词汇被移除）
                    if self.ban_pattern:
                        original_merged_text = merged_text
                        merged_text = self.ban_pattern.sub('', merged_text)
                    
                    await self.tts_queue.put(merged_text)
                    await self.send_text_queue.put('我的文本回复：' + merged_text)
                    logging.info(f'处理剩余数据：{merged_text}')
                    self.current_text = []
                
                # 重置终止字符为初始状态以准备下一批次
                if not self.use_initial_chars:
                    self.use_initial_chars = True
                
                logging.info('队列空闲，已重置处理状态。')

    def find_first_termination_char(self, text: str, termination_chars: list) -> int:
        """
        查找文本中任一终止字符的第一个出现位置。
        :param text: 要搜索的文本。
        :param termination_chars: 终止字符列表。
        :return: 第一个终止字符的索引，若未找到则返回-1。
        """
        indices = [text.find(char) for char in termination_chars if char in text]
        return min(indices) if indices else -1
    
    def reset(self):
        self.current_text = []
