# notification_utils.py

import aiohttp
from config import logger


async def notify_spring(http_session, endpoint_url, payload):
    """
    Spring 서버에 결과를 비동기적으로 알립니다.
    """
    try:
        async with http_session.post(endpoint_url, json=payload) as resp:
            response_text = await resp.text()
            if resp.status == 200:
                logger.info(f"[Notify] Spring 서버로 결과 전송 성공: {response_text}")
            else:
                logger.error(f"[Notify] Spring 서버 전송 실패 - 상태 코드 {resp.status}: {response_text}")
                raise RuntimeError(f"Spring 서버 전송 실패: {resp.status} - {response_text}")
    except Exception as e:
        logger.error(f"[Notify Error] Spring 서버 알림 중 오류 발생: {e}")
        raise
