import soundfile as sf
import pyrubberband as pyrb
import numpy as np
import asyncio
import os
from pydub import AudioSegment
from config import cpu_executor, logger, S3_BUCKET
from aws_utils import upload_to_s3
import io

def run_remix_sync(input_path, output_dir, tempo, pitch, chorus, space):
    """
    Remix를 동기적으로 실행하여 음원을 스템 분리합니다.
    """
    try:
        y, sr = sf.read(input_path)

        if len(y.shape) > 1:
            y = y.mean(axis=1)
        logger.info("[Remix] 리믹스 파일 변환 완료")

        if tempo != 1.0:
            y = pyrb.time_stretch(y, sr, tempo)
        logger.info("[Remix] 리믹스 템포 적용 완료")

        if pitch != 0:
            y = pyrb.pitch_shift(y, sr, pitch)
        logger.info("[Remix] 리믹스 피치 적용 완료")

        if chorus:
            delay_samples1 = int(0.03 * sr)  # 30ms
            delay_samples2 = int(0.06 * sr)  # 60ms

            chorus1 = np.pad(y, (delay_samples1, 0))[:-delay_samples1]
            chorus2 = np.pad(y, (delay_samples2, 0))[:-delay_samples2]

            y = y + 0.5 * chorus1 + 0.5 * chorus2
            y = y / np.max(np.abs(y))
        logger.info("[Remix] 리믹스 코러스 적용 완료")

        if space != 0:
            # 여러 개의 짧은 딜레이로 공간감 생성
            delays = [15, 30, 45]  # ms
            decays = [0.3, 0.2, 0.1]  # 각 딜레이의 감쇠율

            y_reverb = np.zeros_like(y)
            for delay_ms, decay in zip(delays, decays):
                delay_samples = int(delay_ms * sr / 1000)
                delayed = np.pad(y, (delay_samples, 0))[:-delay_samples]
                y_reverb += delayed * decay

            # 원본과 공간감 효과 믹스 (value는 0.0 ~ 1.0 사이)
            y = (1 - space) * y + space * y_reverb
            y = y / np.max(np.abs(y))  # 노멀라이즈
        logger.info("[Remix] 리믹스 리버브 적용 완료")

        output_file = os.path.join(output_dir, "remix_" +  os.path.basename(input_path))
        save_audio(y, sr, output_file)
        logger.info(f"[Remix] 리믹스 작업 완료: {output_file}")

        return output_file
    except Exception as e:
        logger.error(f"[Remix Error] Remix 실행 실패: {e}")
        raise RuntimeError(f"Remix 실행 실패: {e}")

async def run_remix_async(input_path, output_dir, body, session):
    """
    Remix 작업을 비동기적으로 실행하는 래퍼 함수.
    """

    loop = asyncio.get_event_loop()
    output_file = await loop.run_in_executor(
        cpu_executor,
        run_remix_sync,
        input_path,
        output_dir,
        body["tempoRatio"],
        body["scaleModulation"],
        body["isChorusOn"],
        body["reverbAmount"]
    )

    return await remix_upload_async(session, body, output_file)

async def remix_upload_async(session, body, result_file):
    """
    Demucs S3 업로드 및 Spring Server 에 제공할 payload 생성 함수.
    """
    task_id = body["taskId"]
    payload = {
        "taskId": task_id,
    }

    async with session.client('s3') as s3_ul_client:
        result_key = f"resultFiles/{task_id}/{os.path.basename(result_file)}"
        await upload_to_s3(s3_ul_client, S3_BUCKET, result_key, result_file)

    payload["resultMusicUrl"] = f"https://{S3_BUCKET}.s3.amazonaws.com/{result_key}"
    return payload

def save_audio(y, sr, output_path):
    """오디오 저장 (WAV -> MP3 변환 포함)"""
    # 임시 WAV 파일로 저장
    temp_wav = io.BytesIO()
    sf.write(temp_wav, y, sr, format='WAV')
    temp_wav.seek(0)

    # WAV를 MP3로 변환
    audio_segment = AudioSegment.from_wav(temp_wav)
    audio_segment.export(output_path, format='mp3')
