# config.py

import os
import logging
import torch
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor

# 환경 변수 로드
load_dotenv()

# 환경 변수 설정
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
S3_BUCKET = os.getenv("S3_BUCKET")
SPRING_ENDPOINT = os.getenv("SPRING_ENDPOINT")

MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))
MAX_DEMUCS_WORKERS = int(os.getenv("MAX_DEMUCS_WORKERS", "5"))

# 멀티프로세싱용 실행자
executor = ProcessPoolExecutor(max_workers=MAX_DEMUCS_WORKERS)

# device 설정
if torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('worker.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"[INFO] device initiated: {device}")
