# task_processor.py

import tempfile
import shutil
import os
import aiohttp
import json

from src.config import SQS_QUEUE_URL, S3_BUCKET, SPRING_ENDPOINT, logger, aws_session
from src.utils.track_utils import run_demucs_async
from src.utils.remix_utils import run_remix_async
from src.utils.harmony_utils import run_harmony_async
from src.utils.aws_utils import download_from_s3
from src.utils.notification_utils import notify_spring
from src.utils.file_utils import replace_spaces_in_filename
from src.utils.discord_bot import send_message


async def process_message(sqs_client, message, semaphore):
    """
    Asynchronously processes a message from an SQS queue.

    This function handles the processing of a received SQS message by performing
    the following steps:
    1. Downloads the audio file from an S3 bucket.
    2. Executes additional tasks based on the type of the job in the message.
    3. Notifies a Spring server about the status and outcome of the task.
    4. Deletes the processed message from the SQS queue.
    5. Cleans up temporary resources created during processing.

    Parameters:
        sqs_client (Any): The SQS client used for interacting with the SQS queue.
        message (Dict): The message received from the SQS queue to be processed.
        semaphore (Any): An asyncio semaphore to throttle the concurrent execution
            of this function.

    Raises:
        ValueError: If an unsupported task type is identified in the message body.

    """

    async with semaphore:
        # SQS 메시지 처리 시작
        receipt_handle = message['ReceiptHandle']
        body = json.loads(message['Body'].strip())

        # 메시지 파싱
        s3_key = body["key"]
        task_id = body["taskId"]
        task_type = body["jobType"]

        logger.info(f"[Process] 메시지 수신: {body}")
        try:
            await send_message(f"[Process] 메시지 수신: {body}")
            logger.info(f"[Discord] 메시지 전송 성공")
        except Exception as e:
            logger.error(f"[Discord] 메시지 전송 실패: {e}")

        # 임시 디렉토리 생성
        tmp_output_dir = tempfile.mkdtemp()
        input_path = os.path.join(tmp_output_dir, os.path.basename(s3_key))

        # 엔드포인트 분리
        endpoint = SPRING_ENDPOINT

        try:
            # 1. S3에서 음원 파일 다운로드
            async with aws_session.client('s3') as s3_dl_client:
                key = "requestFiles/" + str(body["musicId"]) + "/" + s3_key
                await download_from_s3(s3_dl_client, S3_BUCKET, key, input_path)
            input_path = replace_spaces_in_filename(input_path)

            # 2. Task 처리
            if task_type == "TRACK":
                # Demucs 로 스템 분리
                payload = await run_demucs_async(input_path, tmp_output_dir, body)

                # 엔드포인트 분리
                endpoint += "tracks"

            elif task_type == "HARMONY":
                payload = await run_harmony_async(input_path, body)

                endpoint += "harmony"
            elif task_type == "REMIX":
                payload = await run_remix_async(input_path, tmp_output_dir, body)

                endpoint += "remix"
            else:
                raise ValueError(f"지원되지 않는 작업 유형입니다: {task_type}")

        except Exception as e:
            logger.error(f"[Error] 메시지 처리 중 예외 발생: {e}")
            endpoint += "fail"
            # 실패 시 payload 구조 설정
            payload = {
                "taskId": task_id,
                "failMessage": str(e)
            }

        finally:
            # 4. Spring 서버에 알림
            try:
                async with aiohttp.ClientSession() as http_session:
                    await notify_spring(http_session, endpoint, payload)
                try:
                    await send_message(f"[Process] 메세지 처리 및 스프링 전송 완료: {payload}")
                    logger.info(f"[Discord] 메시지 전송 성공")
                except Exception as e:
                    logger.error(f"[Discord] 메시지 전송 실패: {e}")
            except Exception as e:
                try:
                    await send_message(f"[Process] 메세지 처리 및 스프링 전송 실패: {payload}")
                    logger.info(f"[Discord] 메시지 전송 성공")
                except Exception as e:
                    logger.error(f"[Discord] 메시지 전송 실패: {e}")
            finally:
                # 5. SQS 메시지 삭제
                try:
                    await sqs_client.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
                finally:
                    logger.info(f"[Delete] SQS 메시지 삭제 완료: task_id = {task_id}")
                    # 임시 디렉토리 정리
                    logger.info(f"[Cleanup] 임시 디렉토리 삭제: {tmp_output_dir}")
                    shutil.rmtree(tmp_output_dir, ignore_errors=True)