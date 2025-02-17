import essentia
import essentia.standard as es
import numpy as np
from config import frame_size, hop_size, sample_rate, windowing, spectrum, mfcc, rms, logger, minor_keys, major_keys, notes, cpu_executor
import asyncio

def run_harmony_sync(input_path):
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

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        cpu_executor,
        run_harmony_sync,
        input_path
    )

    return harmony_get_payload(body, result)

def harmony_get_payload(body, result):
    task_id = body["taskId"]

    return {
        "taskId": task_id,
        "scale": result["key"] + ": " + result["component"],
        "bpm": result["bpm"],
        "genre": result["genre"],
        "voiceColor": result["brightness"]
    }

def get_relative_key(key, scale):
    """주어진 키의 관계조를 반환"""

    if scale == 'major':
        idx = major_keys.index(key)
        return f"{key} major({minor_keys[idx]} minor)"
    else:  # minor
        idx = minor_keys.index(key)
        return f"{key} minor({major_keys[idx]} major)"

def get_scale_notes(key, scale):
    """키와 스케일에 따른 구성음 반환"""

    # 시작 음의 인덱스 찾기
    start_idx = notes.index(key)

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
