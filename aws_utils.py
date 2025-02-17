# aws_utils.py

import aiohttp
import asyncio
import os
import aioboto3
from config import logger

session = aioboto3.Session()  # 세션을 모듈 전역으로 사용 (원하면 worker.py 내부에서 생성해도 됨)


async def download_from_s3(s3_client, bucket, key, download_path):
    """
    S3에서 파일을 비동기적으로 다운로드합니다.
    """
    try:
        await s3_client.download_file(Bucket=bucket, Key=key, Filename=download_path)
        logger.info(f"[Download] S3에서 {key} -> {download_path} 다운로드 완료.")
    except Exception as e:
        logger.error(f"[Download Error] S3에서 {key} 다운로드 중 오류: {e}")
        raise


async def upload_to_s3(s3_client, bucket, key, upload_path):
    """
    파일을 S3에 비동기적으로 업로드합니다.
    """
    try:
        await s3_client.upload_file(Filename=upload_path, Bucket=bucket, Key=key)
        file_url = f"https://{bucket}.s3.amazonaws.com/{key}"
        logger.info(f"[Upload] {upload_path} -> S3의 {key} 업로드 완료. URL: {file_url}")
        return file_url
    except Exception as e:
        logger.error(f"[Upload Error] {upload_path} 업로드 중 오류 발생: {e}")
        raise
