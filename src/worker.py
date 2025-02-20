# src/worker.py

import asyncio

from src.task_processor import process_message
from src.config import SQS_QUEUE_URL, MAX_CONCURRENT_TASKS, logger, aws_session
from src.utils.discord_bot import run_bot, send_message


async def worker():
    """
    SQS에서 메시지를 폴링하고 처리하는 워커 함수.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    logger.info("ALL INITIALIZED. GPU WORKER IS READY.")

    async with aws_session.client('sqs') as sqs_client:
        while True:
            try:
                response = await sqs_client.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=5,  # 한 번에 가져올 메시지 수 (최대 10)
                    WaitTimeSeconds=20,  # 롱 폴링 (최대 20초)
                    VisibilityTimeout=120  # 메시지 가시성 타임아웃 (초)
                )

                messages = response.get('Messages', [])
                if not messages:
                    continue  # 새로운 메시지가 없으면 다시 폴링

                logger.info(f"[Receive] {len(messages)}개의 메시지 수신")

                # 각 메시지를 비동기적으로 처리
                for msg in messages:
                    asyncio.create_task(process_message(sqs_client, msg, semaphore))

            except Exception as e:
                logger.error(f"[Error] 워커 루프 중 예외 발생: {e}")
                try:
                    await send_message(f"[Error] 워커 루프 중 예외 발생: {e}")
                except Exception as e:
                    logger.error(f"[Discord] 메시지 전송 실패: {e}")
                await asyncio.sleep(5)  # 예외 발생 시 잠시 대기 후 재시도


async def main():
    """
    메인 함수: 워커를 시작합니다.
    """
    bot_task = asyncio.create_task(run_bot())
    worker_task = asyncio.create_task(worker())

    await asyncio.gather(worker_task, bot_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except asyncio.CancelledError:
        logger.info("워커가 취소되었습니다.")
    except Exception as e:
        logger.error(f"[Fatal Error] 워커 실행 중 치명적인 오류 발생: {e.__class__.__name__}")
