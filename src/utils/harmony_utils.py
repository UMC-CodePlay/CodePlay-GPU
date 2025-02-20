# src/harmony_utils.py

import asyncio
import essentia.standard as es
import numpy as np

from src.config import (
    frame_size, hop_size, sample_rate, windowing, spectrum, mfcc, rms, logger,
    minor_keys, major_keys, notes, cpu_executor, major_mapping, minor_mapping, note_mapping)



def run_harmony_sync(input_path):
    """
    Performs harmonic analysis and audio feature extraction on the given input audio file.

    The function processes the provided audio file to extract various musical features, including
    key, scale, tempo (bpm), timbre, and other characteristics. It uses these extracted features
    to infer musical properties such as brightness, timbre complexity, and stability, as well
    as to predict the potential genre of the music. Additionally, the function processes frame-level
    analysis for energy profile and performs feature calculations based on MFCC (Mel Frequency
    Cepstral Coefficients).

    Parameters:
        input_path (str): Path to the audio file to be processed.

    Returns:
        dict: A dictionary containing various musical features and their computed values.

    Raises:
        RuntimeError: Raised if the harmonic analysis or any part of the extraction process fails.
    """

    try:
        loader = es.MonoLoader(filename=input_path, sampleRate=sample_rate)
        audio = loader()
        logger.info("[Harmony] 하모니 파일 변환 완료")

        result_dict = {}

        key_extractor = es.KeyExtractor()
        key, scale, key_strength = key_extractor(audio)
        result_dict["key"] = get_relative_key(key, scale)
        result_dict["component"] = get_scale_notes(key, scale)
        result_dict["key_strength"] = key_strength
        logger.info("[Harmony] 하모니 키 추출 완료")

        rhythm_extractor = es.RhythmExtractor2013()
        bpm, beats, beats_confidence, _, _ = rhythm_extractor(audio)
        result_dict["bpm"] = int(bpm)
        result_dict["bpm_strength"] = beats_confidence
        logger.info("[Harmony] 하모니 bpm 추출 완료")

        energy_profile = []
        mfccs = []
        # 프레임별 분석
        for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
            windowed_frame = windowing(frame)
            spec = spectrum(windowed_frame)
            energy = rms(frame)
            energy_profile.append(energy)
            # MFCC 계산
            mfcc_bands, mfcc_coeffs = mfcc(spec)
            mfccs.append(mfcc_coeffs)
        # MFCC 기반 음악 특성 분석
        mfcc_array = np.array(mfccs)
        mfcc_mean = np.mean(mfcc_array, axis=0)
        mfcc_std = np.std(mfcc_array, axis=0)
        # 음색의 안정성 (낮을수록 안정적)
        timbre_stability = np.mean(mfcc_std[1:])
        # 음색의 밝기
        brightness = np.mean(mfcc_mean[1:6])
        # 음색의 복잡도
        complexity = np.sum(np.abs(mfcc_mean[6:]))
        result_dict["timbre_stability"] = "high" if timbre_stability < 20 else "medium" if timbre_stability < 40 else "low"
        result_dict["brightness"] = "bright" if brightness > 0 else "dark"
        logger.info("[Harmony] 하모니 음색 추출 완료")
        result_dict["complexity"] = "simple" if complexity < 100 else "medium"if complexity < 200 else "complex"
        # 장르 추정
        if timbre_stability < 20:
            if complexity < 100:
                result_dict["genre"] = "classic"
            elif complexity > 200:
                result_dict["genre"] = "jazz"
            else:
                result_dict["genre"] = "pop"
        elif timbre_stability > 40:
            if complexity > 150:
                result_dict["genre"] = "rock or jazz"
        else:
            if complexity > 180:
                result_dict["genre"] = "electronic"
            else:
                result_dict["genre"] = "pop"
        logger.info("[Harmony] 하모니 장르 추출 및 전체 실행 완료")

        return result_dict
    except Exception as e:
        logger.error(f"[Harmony Error] Harmony 실행 실패: {e}")
        raise RuntimeError(f"Harmony 실행 실패: {e}")

async def run_harmony_async(input_path, body):
    """
    Executes the Harmony application asynchronously with the given input path
    and body, leveraging an event loop to run the synchronous version of Harmony
    in an executor, and retrieves the output payload.

    Args:
        input_path: The file path to the input data for the Harmony process.
        body: The additional data payload required for processing.

    Returns:
        The payload output processed by the Harmony application.

    Raises:
        None explicitly specified.
    """

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        cpu_executor,
        run_harmony_sync,
        input_path
    )

    return harmony_get_payload(body, result)

def harmony_get_payload(body, result):
    """
    Generate a payload dictionary that includes specific musical analysis data.
    The function extracts the task ID from the input body, combines specific
    result components, and maps various musical attributes to corresponding
    properties in the output dictionary.

    Args:
        body (dict): A dictionary containing the task details including the taskId.
        result (dict): A dictionary with analysis results including keys
                       like 'key', 'component', 'bpm', 'genre', and 'brightness'.

    Returns:
        dict: A dictionary containing the taskId and musical analysis attributes
        such as scale, bpm, genre, and voiceColor.
    """

    task_id = body["taskId"]

    return {
        "taskId": task_id,
        "scale": result["key"] + ": " + result["component"],
        "bpm": result["bpm"],
        "genre": result["genre"],
        "voiceColor": result["brightness"]
    }

def get_relative_key(key, scale):
    """
    Determine the relative key based on the given key and scale.

    This function calculates the corresponding relative key between
    major and minor scales. If the provided scale is 'major', it
    returns the relative minor key for the given major key.
    Similarly, if the scale is 'minor', it returns the relative major
    key for the given minor key.

    Parameters:
    key: str
        The musical key for which the relative key needs to be
        determined.
    scale: str
        The scale type, either 'major' or 'minor'. Determines the
        scale in which the relative key should be found.

    Returns:
    str
        A string representing the relative key in the format
        "{key} major({relative_key} minor)" for major scales
        and "{key} minor({relative_key} major)" for minor scales.
    """

    if scale == 'major':
        idx = major_mapping[key]
        return f"{key} major({minor_keys[idx]} minor)"
    else:  # minor
        idx = minor_mapping[key]
        return f"{key} minor({major_keys[idx]} major)"

def get_scale_notes(key, scale):
    """
    Generates notes for a given musical key and scale.

    This function calculates the notes of a scale based on a starting
    key and a scale type (major or minor). It works by determining the
    intervals corresponding to the scale type and applying them to the
    starting key to produce the notes of the scale.

    Parameters:
    key : str
        The starting note of the scale (e.g., 'C', 'D#', 'F').
    scale : str
        The type of scale to generate, either 'major' or 'minor'.

    Returns:
    str
        A string of notes in the specified scale separated by ' - '.

    Raises:
    ValueError
        If the input key is not found in the predefined list of notes.
    TypeError
        If the provided parameters are not of the expected type (e.g.,
        key is not a string, scale is not a string).
    """

    # 시작 음의 인덱스 찾기
    start_idx = note_mapping[key]

    # 스케일에 따른 음정 간격
    if scale == 'major':
        intervals = [0, 2, 4, 5, 7, 9, 11]  # 장음계 간격
    else:  # minor
        intervals = [0, 2, 3, 5, 7, 8, 10]  # 단음계 간격

    # 구성음 생성
    scale_notes = []
    for interval in intervals:
        note_idx = (start_idx + interval) % 12
        scale_notes.append(notes[note_idx])

    return ' - '.join(scale_notes)
