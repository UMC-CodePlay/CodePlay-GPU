# demucs_utils.py

import subprocess
import os
import asyncio
from config import device, executor, logger


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
    command += [device, "-o", output_dir, input_path]

    logger.info(f"[Demucs] 명령어 실행: {' '.join(command)}")
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"[Demucs] 스템 분리 완료: {input_path}")
        logger.debug(f"[Demucs Output] {process.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"[Demucs Error] Demucs 실행 실패: {e.stderr}")
        raise RuntimeError(f"Demucs 실행 실패: {e.stderr}")


async def run_demucs_async(input_path, output_dir, two_stem_config):
    """
    Demucs를 비동기적으로 실행하기 위한 래퍼 함수.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        executor,
        run_demucs_sync,
        input_path,
        output_dir,
        two_stem_config
    )

    # Demucs 출력 폴더에서 스템 파일 경로 찾기
    original_filename = os.path.splitext(os.path.basename(input_path))[0]
    if two_stem_config in ["guitar", "piano"]:
        result_folder = os.path.join(output_dir, "htdemucs_6s", original_filename)
    else:
        result_folder = os.path.join(output_dir, "htdemucs", original_filename)
    if not os.path.isdir(result_folder):
        raise FileNotFoundError(f"Demucs 결과 폴더가 존재하지 않습니다: {result_folder}")

    return result_folder

async def demucs_upload_async(client, ):
    """
    Demucs S3 업로드 및 Spring Server 에 제공할 payload 생성 함수.
    """

    async with
