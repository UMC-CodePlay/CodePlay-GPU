# src/config.py

import os
import logging
import torch
import essentia.standard as es
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path



# 프로젝트 루트 경로 (config.py 기준으로 두 단계 상위: src/ 상위가 ProjectRoot/)
BASE_DIR = Path(__file__).resolve().parent.parent

# .env .log 파일 경로
ENV_PATH = BASE_DIR / ".env"
LOG_FILE = BASE_DIR / "worker.log"  # 절대 경로로 로그 파일 지정

# 환경 변수 로드
load_dotenv(dotenv_path=ENV_PATH)

# 환경 변수 설정
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
S3_BUCKET = os.getenv("S3_BUCKET")
SPRING_ENDPOINT = os.getenv("SPRING_ENDPOINT")

MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "7"))
MAX_GPU_WORKERS = int(os.getenv("MAX_DEMUCS_WORKERS", "2"))
MAX_CPU_WORKERS = int(os.getenv("MAX_CPU_WORKERS", "5"))

# 멀티프로세싱용 실행자
gpu_executor = ProcessPoolExecutor(max_workers=MAX_GPU_WORKERS)
cpu_executor = ProcessPoolExecutor(max_workers=MAX_CPU_WORKERS)

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
        logging.FileHandler(str(LOG_FILE), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"GPU device initiated: {device}")

# 하모니 사전 변수
frame_size = 2048
hop_size = 1024
sample_rate = 44100

windowing = es.Windowing(type='hann', size=frame_size)
spectrum = es.Spectrum()
mfcc = es.MFCC(
    inputSize=frame_size//2 + 1,
    numberBands=40,
    numberCoefficients=13,
    sampleRate=sample_rate,
    lowFrequencyBound=20,
    highFrequencyBound=20000
)
rms = es.RMS()

major_keys = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'F', 'Bb', 'Eb', 'Ab']
minor_keys = ['A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'D', 'G', 'C', 'F']
notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']