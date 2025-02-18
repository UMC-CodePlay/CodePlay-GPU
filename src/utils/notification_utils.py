# src/notification_utils.py

from src.config import logger


async def notify_spring(http_session, endpoint_url, payload):
    """
    Sends a notification to the Spring server using an HTTP POST request.

    This asynchronous function sends a JSON payload to a specified endpoint of a
    Spring server and logs the response or any errors encountered during the process.
    If the response status code indicates a failure, an exception is raised.

    Parameters:
    -----------
    http_session : aiohttp.ClientSession
        The asynchronous HTTP client session to use for sending the post request.
    endpoint_url : str
        The URL of the Spring server endpoint to which the payload will be sent.
    payload : dict
        The JSON-compatible dictionary payload to send in the POST request.

    Raises:
    -------
    RuntimeError
        If the HTTP response from the server is unsuccessful (status not 200).
    Exception
        If any error occurs during the request or response processing.

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
