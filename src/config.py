# src/config.py

import os
import logging
import torch
import essentia.standard as es
import aioboto3
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
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # 메시지를 보낼 특정 채널의 ID

MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "7"))
MAX_GPU_WORKERS = int(os.getenv("MAX_DEMUCS_WORKERS", "2"))
MAX_CPU_WORKERS = int(os.getenv("MAX_CPU_WORKERS", "5"))

# 멀티프로세싱용 실행자
gpu_executor = ProcessPoolExecutor(max_workers=MAX_GPU_WORKERS)
cpu_executor = ProcessPoolExecutor(max_workers=MAX_CPU_WORKERS)

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

device = 'cuda'

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

# 모든 가능한 표기(동음이의어)를 포함한 매핑 딕셔너리:
major_mapping = {
    'C': 0,
    'G': 1,
    'D': 2,
    'A': 3,
    'E': 4,
    'B': 5,
    'F#': 6, 'Gb': 6,      # F#와 Gb는 같은 위치(인덱스 6)
    'Db': 7, 'C#': 7,      # Db와 C#은 같은 위치(인덱스 7)
    'F': 8,
    'Bb': 9, 'A#': 9,
    'Eb': 10, 'D#': 10,
    'Ab': 11 , 'G#': 11,
}

minor_mapping = {
    'A': 0,
    'E': 1,
    'B': 2,
    'F#': 3, 'Gb': 3,      # F# minor와 Gb minor (실제로 Gb minor는 드물지만 enharmonic 처리)
    'C#': 4, 'Db': 4,      # C# minor와 Db minor
    'G#': 5, 'Ab': 5,      # G# minor와 Ab minor
    'D#': 6, 'Eb': 6,      # D# minor와 Eb minor
    'Bb': 7, 'A#': 7,      # Bb minor와 A# minor
    'D': 8,
    'G': 9,
    'C': 10,
    'F': 11
}

note_mapping = {
    'C': 0,
    'C#': 1, 'Db': 1,
    'D': 2,
    'D#': 3, 'Eb': 3,
    'E': 4,
    'F': 5,
    'F#': 6, 'Gb': 6,
    'G': 7,
    'G#': 8, 'Ab': 8,
    'A': 9,
    'A#': 10, 'Bb': 10,
    'B': 11
}


# 세션
aws_session = aioboto3.Session()
