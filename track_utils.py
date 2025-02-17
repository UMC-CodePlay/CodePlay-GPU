# track_utils.py

import subprocess
import os
import asyncio
from config import device, executor, logger, S3_BUCKET
from aws_utils import upload_to_s3


def run_demucs_sync(input_path, output_dir, two_stem_config):
    """
    Demucs를 동기적으로 실행하여 음원을 스템 분리합니다.
    """
    # task_type을 Command line 인자로 그대로 쓴다고 가정
    command = ["demucs"]
    if two_stem_config in ["vocals", "bass", "drums"]:
        command += ["--two-stems", two_stem_config, "-d"]
    elif two_stem_config in ["guitar", "piano"]:
        command += ["-n", "htdemucs_6s", "--two-stems", two_stem_config, "-d"]
    else:
        command += ["-d"]
    command += [device, "-o", output_dir, input_path]

    logger.info(f"[Demucs] 명령어 실행: {' '.join(command)}")
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"[Demucs] 스템 분리 완료: {input_path}")
        logger.debug(f"[Demucs Output] {process.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"[Demucs Error] Demucs 실행 실패: {e.stderr}")
        raise RuntimeError(f"Demucs 실행 실패: {e.stderr}")


async def run_demucs_async(input_path, output_dir, body, session):
    """
    Demucs를 비동기적으로 실행하기 위한 래퍼 함수.
    """

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        executor,
        run_demucs_sync,
        input_path,
        output_dir,
        body["twoStemConfig"]
    )

    # Demucs 출력 폴더에서 스템 파일 경로 찾기
    original_filename = os.path.splitext(os.path.basename(input_path))[0]
    if body["twoStemConfig"] in ["guitar", "piano"]:
        result_folder = os.path.join(output_dir, "htdemucs_6s", original_filename)
    else:
        result_folder = os.path.join(output_dir, "htdemucs", original_filename)
    if not os.path.isdir(result_folder):
        raise FileNotFoundError(f"Demucs 결과 폴더가 존재하지 않습니다: {result_folder}")

    return await demucs_upload_async(session, body, result_folder)


async def demucs_upload_async(session, body, result_folder):
    """
    Demucs S3 업로드 및 Spring Server 에 제공할 payload 생성 함수.
    """
    task_id = body["taskId"]
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
    print(payload)
    return payload
