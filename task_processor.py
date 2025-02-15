# task_processor.py

import asyncio
import tempfile
import shutil
import os
import aiohttp
import json

from config import SQS_QUEUE_URL, S3_BUCKET, SPRING_ENDPOINT, logger
from demucs_utils import run_demucs_async
from aws_utils import download_from_s3, upload_to_s3, session
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
                result_folder = await run_demucs_async(input_path, tmp_output_dir, body["twoStemConfig"])

                # 3. 결과 파일을 업로드 / payload
                payload = {
                    "taskId": task_id,
                    "isTwoStem": not (body["twoStemConfig"] == "none")
                }
                upload_tasks = []
                async with session.client('s3') as s3_ul_client:
                    for result_file in os.listdir(result_folder):
                        result_path = os.path.join(result_folder, result_file)
                        result_key = f"resultFiles/{task_id}/{result_file}"
                        upload_tasks.append(
                            upload_to_s3(s3_ul_client, S3_BUCKET, result_key, result_path)
                        )
                        tmp = result_file.split(".")[0]
                        if tmp == "vocals":
                            payload["vocalUrl"] = f"https://{S3_BUCKET}.s3.amazonaws.com/{result_key}"
                        elif tmp == "bass":
                            payload["bassUrl"] = f"https://{S3_BUCKET}.s3.amazonaws.com/{result_key}"
                        elif tmp == "drums":
                            payload["drumsUrl"] = f"https://{S3_BUCKET}.s3.amazonaws.com/{result_key}"
                        elif tmp == "guitar":
                            payload["guitarUrl"] = f"https://{S3_BUCKET}.s3.amazonaws.com/{result_key}"
                        elif tmp == "piano":
                            payload["pianoUrl"] = f"https://{S3_BUCKET}.s3.amazonaws.com/{result_key}"
                        else:
                            payload["instrumentalUrl"] = f"https://{S3_BUCKET}.s3.amazonaws.com/{result_key}"
                    # 모든 업로드를 동시에 실행
                    await asyncio.gather(*upload_tasks)

                # 엔드포인트 분리
                endpoint += "tracks"

            elif task_type == "HARMONY":
                raise NotImplementedError("harmony 작업은 아직 구현되지 않았습니다.")
            elif task_type == "REMIX":
                raise NotImplementedError("remix 작업은 아직 구현되지 않았습니다.")
            else:
                raise ValueError(f"지원되지 않는 작업 유형입니다: {task_type}")

        except Exception as e:
            logger.error(f"[Error] 메시지 처리 중 예외 발생: {e}")
            endpoint += "fail"
            # 4. Spring 서버에 결과 알림(실패)
            payload = {
                "taskId": task_id,
                "failMessage": str(e)
            }
            async with aiohttp.ClientSession() as http_session:
                await notify_spring(http_session, endpoint, payload)

        else:
            # 4. Spring 서버에 결과 알림(성공)
            print(payload)
            async with aiohttp.ClientSession() as http_session:
                await notify_spring(http_session, endpoint, payload)

            # 5. SQS 메시지 삭제
            await sqs_client.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
            logger.info(f"[Delete] SQS 메시지 삭제 완료: {receipt_handle}")

        finally:
            # 임시 디렉토리 정리
            logger.info(f"[Cleanup] 임시 디렉토리 삭제: {tmp_output_dir}")
            shutil.rmtree(tmp_output_dir, ignore_errors=True)
