# src/remix_utils.py

import soundfile as sf
import pyrubberband as pyrb
import numpy as np
import asyncio
import os
import io

from pydub import AudioSegment
from src.config import cpu_executor, logger, S3_BUCKET
from src.utils.aws_utils import upload_to_s3


def run_remix_sync(input_path, output_dir, tempo, pitch, chorus, space):
    """
    Processes an audio input file to apply transformations such as tempo, pitch,
    chorus, and spatial effects, and then saves the resulting modified audio
    file to a specified output directory.

    This function reads an audio input file, optionally adjusts its tempo and pitch,
    applies chorus effects, and adds spatial effects (reverberation) based on
    the parameters provided. The output audio is normalized to avoid clipping,
    ensuring the modified file has balanced sound. The resulting audio file is
    saved with a generated filename in the specified output directory.

    Parameters:
        input_path: str
            Path to the input audio file for remixing.
        output_dir: str
            Path to the directory where the remixed audio file is saved.
        tempo: float
            Tempo adjustment factor. A value of 1.0 applies no change,
            values greater than 1.0 speed up the audio, and values
            less than 1.0 slow it down.
        pitch: float
            Pitch adjustment in semitones. A value of 0 applies no change.
        chorus: bool
            Flag indicating whether to apply chorus effects. If True,
            enables chorus processing.
        space: float
            Intensity of spatial effects (reverberation), range [0.0, 1.0].
            A value closer to 0 applies less effect, while 1.0 applies
            full space simulation.

    Returns:
        str
            Path to the saved remixed audio file.

    Raises:
        RuntimeError
            If an error occurs during remix processing or file operations,
            this error is raised with details logged.
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
        save_audio(y, sr, str(output_file))
        logger.info(f"[Remix] 리믹스 작업 완료: {output_file}")

        return output_file
    except Exception as e:
        logger.error(f"[Remix Error] Remix 실행 실패: {e}")
        raise RuntimeError(f"Remix 실행 실패: {e}")

async def run_remix_async(input_path, output_dir, body, session):
    """
    Asynchronously runs the remix process on the given input file, applying audio
    modifications based on provided parameters, and uploads the processed file
    to a specified location.

    Parameters:
        input_path (str): The file path of the input audio file to be processed.
        output_dir (str): The directory where the processed audio file will be saved.
        body (dict): A dictionary containing the following keys and their
            respective values for audio processing:
                - tempoRatio (float): The ratio to modify the tempo of the audio.
                - scaleModulation (bool): Whether to apply scale modulation.
                - isChorusOn (bool): Whether the chorus effect is enabled.
                - reverbAmount (float): The amount of reverb effect to apply.
        session (aiohttp.ClientSession): The asynchronous HTTP session used
            for uploading the processed file.

    Returns:
        Any: The response from the upload process after the remix is completed.

    Raises:
        RuntimeError: Raised if an unexpected error occurs during either the
        remix or upload process.
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
        Asynchronously uploads a remix result file to an S3 bucket and generates a URL.

        This function performs an asynchronous upload of a remix result file to
        a specified S3 bucket using the provided session and client. Once the upload
        is complete, it generates a publicly accessible URL for the stored file and
        returns that URL along with the corresponding task ID in a payload.

        Parameters:
            session (Any): The session object used to create an S3 client for
            uploading the file to an S3 bucket.
            body (Dict): A dictionary containing the task ID under the key 'taskId'.
            result_file (str): The local file path of the remix result file to be
            uploaded.

        Returns:
            Dict: A payload dictionary containing the task ID and the public URL of
            the uploaded result file.

        Raises:
            Exception: Any exception that occurs during the upload process is
            propagated from the `upload_to_s3` function.
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
    """
    Saves an audio signal as an MP3 file. This function first creates a temporary
    WAV file from the provided signal and sample rate, and then converts it to an
    MP3 file at the specified output path.

    Parameters:
        y (ndarray): The audio signal to be saved.
        sr (int): The sample rate of the audio signal.
        output_path (str): The path where the resulting MP3 file will be exported.
    """

    # 임시 WAV 파일로 저장
    temp_wav = io.BytesIO()
    sf.write(temp_wav, y, sr, format='WAV')
    temp_wav.seek(0)

    # WAV를 MP3로 변환
    audio_segment = AudioSegment.from_wav(temp_wav)
    audio_segment.export(output_path, format='mp3')
