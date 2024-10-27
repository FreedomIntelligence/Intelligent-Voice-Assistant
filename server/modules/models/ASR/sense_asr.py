import aiohttp
import logging
from models.ASR.base_asr import BaseASR
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


class SenseASR(BaseASR):
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def post_audio(self, combined_audio: bytes, lang: str = "auto") -> str:
        """
        发送音频到Sense ASR API并返回转录文本。
        """
        url = 'XXX/api/v1/asr'
        try:
            form = aiohttp.FormData()
            form.add_field('files', combined_audio, filename='audio.wav', content_type='audio/wav')
            form.add_field('keys', 'audio.wav')
            form.add_field('lang', lang)

            async with self.session.post(url, data=form) as resp:
                if resp.status == 200:
                    json_resp = await resp.json()
                    if "result" in json_resp and json_resp["result"]:
                        transcribed_text = json_resp["result"][0].get("text", "").strip()
                        logging.info(f"ASR 回复文本: {transcribed_text}")
                        return transcribed_text
                    else:
                        logging.warning("ASR API 返回结果为空或格式不正确。")
                        return ""
                else:
                    error_text = await resp.text()
                    raise Exception(f"ASR API 错误 {resp.status}: {error_text}")
        except Exception as e:
            logging.error(f"SenseASR.post_audio 错误: {e}")
            return ""

    async def close(self):
        pass
