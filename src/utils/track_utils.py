# src/track_utils.py

import subprocess
import os
import asyncio
from src.config import device, gpu_executor, logger, S3_BUCKET, aws_session
from src.utils.aws_utils import upload_to_s3


def run_demucs_sync(input_path, output_dir, two_stem_config):
    """
    Executes the Demucs stem separation process on an audio file synchronously using
    subprocess. The function is configurable for various instrument stems and utilizes
    specific device configurations. It logs the process output and errors for troubleshooting.

    Arguments:
        input_path (str): The file path of the input audio that will undergo stem
                          separation.
        output_dir (str): The directory path where the separated stems will be
                          saved.
        two_stem_config (str): Configuration for selecting specific stems to
                               separate, such as "vocals", "bass", "drums",
                               "guitar", or "piano". Matching configurations
                               determine specific command flags.

    Raises:
        RuntimeError: If the Demucs subprocess execution fails, details are
                      logged and the raised error provides the encountered
                      stderr output.
    """

    # task_type을 Command line 인자로 그대로 쓴다고 가정
    model = "htdemucs"
    command = ["demucs"]
    if two_stem_config in ["vocals", "bass", "drums"]:
        command += ["--two-stems", two_stem_config]
    elif two_stem_config in ["guitar", "piano"]:
        command += ["-n", "htdemucs_6s", "--two-stems", two_stem_config]
        model = "htdemucs_6s"

    command += ["-d", device, "--mp3", "-o", output_dir, input_path]

    logger.info(f"[Demucs] 명령어 실행: {' '.join(command)}")
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"[Demucs] 스템 분리 완료: {input_path}")
        logger.debug(f"[Demucs Output] {process.stdout}")
        return model
    except subprocess.CalledProcessError as e:
        logger.error(f"[Demucs Error] Demucs 실행 실패: {e.stderr}")
        raise RuntimeError(f"Demucs 실행 실패: {e.stderr}")


async def run_demucs_async(input_path, output_dir, body):
    """
    Asynchronously runs the Demucs audio separation process and uploads the resulting separated
    audio files.

    This function utilizes an asynchronous executor to offload the Demucs processing to a
    separate thread or process, allowing the main event loop to remain responsive. Based on
    the `twoStemConfig` value provided in the request body, it determines the specific
    output folder where the separated audio stems are generated and validates its existence.
    If the folder does not exist, an exception is raised. Upon successful processing, the
    result is uploaded using the demucs_upload_async function.

    Args:
        input_path (str): Absolute path to the input audio file to process.
        output_dir (str): Directory path where the Demucs output should be stored.
        body (dict): Request payload containing configuration details such as `twoStemConfig`.

    Returns:
        Any: Result of the demucs_upload_async function, indicating the upload status or response.

    Raises:
        FileNotFoundError: If the expected Demucs result folder does not exist in the output
            directory.
    """

    loop = asyncio.get_event_loop()
    model = await loop.run_in_executor(
        gpu_executor,
        run_demucs_sync,
        input_path,
        output_dir,
        body["twoStemConfig"]
    )

    # Demucs 출력 폴더에서 스템 파일 경로 찾기 //  최적화
    original_filename = os.path.splitext(os.path.basename(input_path))[0]
    result_folder = os.path.join(output_dir, model, original_filename)
    if not os.path.isdir(result_folder):
        raise FileNotFoundError(f"Demucs 결과 폴더가 존재하지 않습니다: {result_folder}")

    return await demucs_upload_async(body, result_folder)


async def demucs_upload_async(body, result_folder):
    """
    Perform asynchronous upload of processed audio files to an S3 bucket and generate a payload
    containing URLs corresponding to the processed audio types.

    This function handles the upload of audio processing results contained in the local directory
    to an S3 bucket using the specified session client. The function identifies the audio types
    based on file naming conventions and includes their respective URLs in the generated payload.
    These URLs point to the uploaded files in the S3 bucket location. Furthermore, the payload
    includes a unique task identifier and a flag whether a two-stem configuration is enabled.

    Parameters:
    body (dict): Dictionary containing details of the upload process such as "taskId" identifying
        the current task and "twoStemConfig" settings which determine if two-stem configuration
        should be applied.
    result_folder (str): Path to the local directory containing the result files to be uploaded
        to the S3 bucket.

    Returns:
    dict: A dictionary containing the task identifier, configuration settings, and corresponding
        S3 file URLs for the processed audio types.

    Raises:
    KeyError: If the "taskId" or "twoStemConfig" is missing in the provided body dictionary.
    """

    task_id = body["taskId"]
    payload = {
        "taskId": task_id,
        "isTwoStem": not (body["twoStemConfig"] == "none")
    }
    upload_tasks = []
    async with aws_session.client('s3') as s3_ul_client:
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
    return payload
