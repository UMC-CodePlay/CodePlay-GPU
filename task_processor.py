# task_processor.py

import asyncio
import tempfile
import shutil
import os
import aiohttp
import json

from config import SQS_QUEUE_URL, S3_BUCKET, SPRING_ENDPOINT, logger
from track_utils import run_demucs_async
from remix_utils import run_remix_async
from harmony_utils import run_harmony_async
from aws_utils import download_from_s3, session
from notification_utils import notify_spring


async def process_message(sqs_client, message, semaphore):
    """
    단일 SQS 메시지를 처리하는 함수.
    """
    async with semaphore:
        # 메시지 처리
        receipt_handle = message['ReceiptHandle']
        body = json.loads(message['Body'].strip())

        # 메시지 파싱
        s3_key = body["key"]
        task_id = body["taskId"]
        task_type = body["jobType"]

        logger.info(f"[Process] 메시지 수신: {body}")

        # 임시 디렉토리 생성
        tmp_output_dir = tempfile.mkdtemp()
        input_path = os.path.join(tmp_output_dir, os.path.basename(s3_key))

        # 엔드포인트 분리
        endpoint = SPRING_ENDPOINT

        try:
            # 1. S3에서 음원 파일 다운로드
            async with session.client('s3') as s3_dl_client:
                await download_from_s3(s3_dl_client, S3_BUCKET, s3_key, input_path)

            # 2. Task 처리
            if task_type == "TRACK":
                # Demucs 로 스템 분리
                payload = await run_demucs_async(input_path, tmp_output_dir, body, session)

                # 엔드포인트 분리
                endpoint += "tracks"

            elif task_type == "HARMONY":
                payload = await run_harmony_async(input_path, body)

                endpoint += "harmony"
            elif task_type == "REMIX":
                payload = await run_remix_async(input_path, tmp_output_dir, body, session)

                endpoint += "remix"
            else:
                raise ValueError(f"지원되지 않는 작업 유형입니다: {task_type}")

        except Exception as e:
            logger.error(f"[Error] 메시지 처리 중 예외 발생: {e}")
            endpoint += "fail"
            # ** 실패할 경우 payload 변경
            payload = {
                "taskId": task_id,
                "failMessage": str(e)
            }

        finally:
            # 4. Spring 서버에 알림
            async with aiohttp.ClientSession() as http_session:
                await notify_spring(http_session, endpoint, payload)
            # 5. SQS 메시지 삭제
            await sqs_client.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
            logger.info(f"[Delete] SQS 메시지 삭제 완료: task_id = {task_id}")
            # 임시 디렉토리 정리
            logger.info(f"[Cleanup] 임시 디렉토리 삭제: {tmp_output_dir}")
            shutil.rmtree(tmp_output_dir, ignore_errors=True)
