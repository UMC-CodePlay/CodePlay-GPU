# worker.py

import asyncio

import aioboto3
import aiohttp
import os
import uuid
import tempfile
import shutil
import logging
import torch
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor
import subprocess

# 환경 변수 로드 / 자동으로 aioboto3에 업로드 됩니다.
load_dotenv()

# 환경 변수 설정
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
S3_BUCKET = os.getenv("S3_BUCKET")
SPRING_ENDPOINT = os.getenv("SPRING_ENDPOINT")
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))
MAX_DEMUCS_WORKERS = int(os.getenv("MAX_DEMUCS_WORKERS", "2"))  # 동시에 실행할 Demucs 프로세스 수

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

# 멀티프로세싱용 실행자
executor = ProcessPoolExecutor(max_workers=MAX_DEMUCS_WORKERS)

# device 설정
if torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"


session = aioboto3.Session()

def run_demucs_sync(input_path, output_dir):
    """
    Demucs를 동기적으로 실행하여 음원을 스템 분리합니다.
    """
    command = ["demucs", "-d", device, "-o", output_dir, input_path]
    logger.info(f"[Demucs] 명령어 실행: {' '.join(command)}")
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"[Demucs] 스템 분리 완료: {input_path}")
        logger.debug(f"[Demucs Output] {process.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"[Demucs Error] Demucs 실행 실패: {e.stderr}")
        raise RuntimeError(f"Demucs 실행 실패: {e.stderr}")


async def run_demucs_async(input_path, output_dir):
    """
    Demucs를 비동기적으로 실행하기 위한 래퍼 함수.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, run_demucs_sync, input_path, output_dir)


async def download_from_s3(s3_client, bucket, key, download_path):
    """
    S3에서 파일을 비동기적으로 다운로드합니다.
    """
    try:
        await s3_client.download_file(Bucket=bucket, Key=key, Filename=download_path)
        logger.info(f"[Download] S3에서 {key}를 {download_path}로 다운로드 완료.")
    except Exception as e:
        logger.error(f"[Download Error] S3에서 {key}를 다운로드하는 중 오류 발생: {e}")
        raise


async def upload_to_s3(s3_client, bucket, key, upload_path):
    """
    파일을 S3에 비동기적으로 업로드합니다.
    """
    try:
        await s3_client.upload_file(Filename=upload_path, Bucket=bucket, Key=key)
        file_url = f"https://{bucket}.s3.amazonaws.com/{key}"
        logger.info(f"[Upload] {upload_path}를 S3의 {key}에 업로드 완료. URL: {file_url}")
        return file_url
    except Exception as e:
        logger.error(f"[Upload Error] {upload_path}를 S3에 업로드하는 중 오류 발생: {e}")
        raise


async def notify_spring(session, payload):
    """
    Spring 서버에 결과를 비동기적으로 알립니다.
    """
    try:
        async with session.post(SPRING_ENDPOINT, json=payload) as resp:
            response_text = await resp.text()
            if resp.status == 200:
                logger.info(f"[Notify] Spring 서버로 결과 전송 성공: {response_text}")
            else:
                logger.error(f"[Notify] Spring 서버 전송 실패 - 상태 코드 {resp.status}: {response_text}")
                raise RuntimeError(f"Spring 서버 전송 실패: {resp.status} - {response_text}")
    except Exception as e:
        logger.error(f"[Notify Error] Spring 서버에 알림을 보내는 중 오류 발생: {e}")
        raise


async def process_message(sqs_client, message, semaphore):
    """
    단일 SQS 메시지를 처리하는 함수.
    """
    async with semaphore:
        receipt_handle = message['ReceiptHandle']
        body = message['Body'].strip()

        # 메시지 형식에 따라 파싱 (예: JSON)
        # 여기서는 간단히 S3 키가 메시지 본문에 있다고 가정
        s3_key = body
        logger.info(f"[Process] 메시지 수신: {s3_key}")

        tmp_dir = tempfile.mkdtemp()
        input_path = os.path.join(tmp_dir, os.path.basename(s3_key))
        demucs_output_dir = os.path.join(tmp_dir, "demucs_output")

        try:
            # 1. S3에서 음원 파일 다운로드
            async with session.client('s3') as s3_client:
                await download_from_s3(s3_client, S3_BUCKET, s3_key, input_path)

            # 2. Demucs로 스템 분리 (GPU 사용)
            await run_demucs_async(input_path, demucs_output_dir)

            # Demucs 출력 폴더에서 스템 파일 경로 찾기
            original_filename = os.path.splitext(os.path.basename(input_path))[0]
            result_folder = os.path.join(demucs_output_dir, "htdemucs", original_filename)
            if not os.path.isdir(result_folder):
                raise FileNotFoundError(f"Demucs 결과 폴더가 존재하지 않습니다: {result_folder}")

            # 3. 스템 파일들을 S3에 업로드
            result_urls = []
            upload_tasks = []
            async with session.client('s3') as s3_upload_client:
                for stem_file in os.listdir(result_folder):
                    stem_path = os.path.join(result_folder, stem_file)
                    unique_id = str(uuid.uuid4())
                    result_key = f"results/{unique_id}/{stem_file}"
                    upload_tasks.append(upload_to_s3(s3_upload_client, S3_BUCKET, result_key, stem_path))

                # 모든 업로드를 동시에 실행
                uploaded_urls = await asyncio.gather(*upload_tasks)
                result_urls.extend(uploaded_urls)

            # 4. Spring 서버에 결과 알림
            payload = {
                "original_file": f"s3://{S3_BUCKET}/{s3_key}",
                "stems": result_urls
            }
            async with aiohttp.ClientSession() as http_session:
                await notify_spring(http_session, payload)

            # 5. SQS 메시지 삭제
            await sqs_client.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
            logger.info(f"[Delete] SQS 메시지 삭제 완료: {receipt_handle}")

        except Exception as e:
            logger.error(f"[Error] 메시지 처리 중 예외 발생: {e}")
            # 메시지를 삭제하지 않으면 Visibility Timeout 후 재처리됩니다.
            # 필요에 따라 Dead Letter Queue(DLQ) 설정을 고려할 수 있습니다.

        finally:
            # 임시 디렉토리 정리
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.info(f"[Cleanup] 임시 디렉토리 삭제: {tmp_dir}")


async def worker():
    """
    SQS에서 메시지를 폴링하고 처리하는 워커 함수.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    while True:
        try:
            async with session.client('sqs') as sqs_client:
                response = await sqs_client.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=10,  # 한 번에 가져올 메시지 수 (최대 10)
                    WaitTimeSeconds=20,  # 롱 폴링 (최대 20초)
                    VisibilityTimeout=60  # 메시지 가시성 타임아웃 (초)
                )

                messages = response.get('Messages', [])
                if not messages:
                    continue  # 새로운 메시지가 없으면 다시 폴링

                logger.info(f"[Receive] {len(messages)}개의 메시지 수신")

                # 각 메시지를 비동기적으로 처리
                tasks = [process_message(sqs_client, msg, semaphore) for msg in messages]
                await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"[Error] 워커 루프 중 예외 발생: {e}")
            await asyncio.sleep(5)  # 예외 발생 시 잠시 대기 후 재시도


async def main():
    """
    메인 함수: 워커를 시작합니다.
    """
    # 시그널 핸들러 설정
    await worker()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except asyncio.CancelledError:
        logger.info("워커가 취소되었습니다.")
    except Exception as e:
        logger.error(f"[Fatal Error] 워커 실행 중 치명적인 오류 발생: {e.__class__.__name__}")
