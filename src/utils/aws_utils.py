# src/aws_utils.py

from src.config import logger


async def download_from_s3(s3_client, bucket, key, download_path):
    """
    Downloads a file from an Amazon S3 bucket to a local path using the provided
    S3 client.

    This asynchronous function uses the provided boto3 S3 client to download a
    file from the specified bucket and key, and saves it to the given local
    download path. In case of an error during the download process, it will log
    an error message and raise the exception.

    Parameters:
        s3_client: The boto3 S3 client to interface with S3.
        bucket: str
            The name of the S3 bucket to download the file from.
        key: str
            The key of the file in the S3 bucket to be downloaded.
        download_path: str
            The local file path where the downloaded file will be saved.

    Raises:
        Exception: If an error occurs during the S3 download process, the
        exception is logged and re-raised for further handling.
    """

    try:
        await s3_client.download_file(Bucket=bucket, Key=key, Filename=download_path)
        logger.info(f"[Download] S3에서 {key} -> {download_path} 다운로드 완료.")
    except Exception as e:
        logger.error(f"[Download Error] S3에서 {key} 다운로드 중 오류: {e}")
        raise


async def upload_to_s3(s3_client, bucket, key, upload_path):
    """
    Asynchronously uploads a file to an S3 bucket and returns the file URL.

    This function uses the provided S3 client to perform an asynchronous file
    upload to the specified S3 bucket and key. If the upload is successful,
    it logs the success and returns the public URL of the uploaded file.
    In case of failure, it logs the error and raises the exception.

    Parameters:
        s3_client (Any): The S3 client instance capable of handling asynchronous
            file uploads.
        bucket (str): The name of the S3 bucket to which the file will be uploaded.
        key (str): The key (path in S3) under which the file will be stored.
        upload_path (str): The local file path of the file to be uploaded.

    Returns:
        str: The public URL of the file uploaded to S3.

    Raises:
        Exception: Raises any exception that occurs during the file upload
            to S3.
    """

    try:
        await s3_client.upload_file(
            Filename=upload_path,
            Bucket=bucket,
            Key=key,
            ExtraArgs={'ContentType': 'audio/mpeg'}
        )
        file_url = f"https://{bucket}.s3.amazonaws.com/{key}"
        logger.info(f"[Upload] {upload_path} -> S3의 {key} 업로드 완료. URL: {file_url}")
        return file_url
    except Exception as e:
        logger.error(f"[Upload Error] {upload_path} 업로드 중 오류 발생: {e}")
        raise
