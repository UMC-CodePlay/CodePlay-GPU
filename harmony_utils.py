import essentia
import essentia.standard as es
import numpy as np

def get_relative_key(key, scale):
    """주어진 키의 관계조를 반환"""
    major_keys = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'F', 'Bb', 'Eb', 'Ab']
    minor_keys = ['A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'D', 'G', 'C', 'F']

    if scale == 'major':
        idx = major_keys.index(key)
        return f"{key} major({minor_keys[idx]} minor)"
    else:  # minor
        idx = minor_keys.index(key)
        return f"{key} minor({major_keys[idx]} major)"

def get_scale_notes(key, scale):
    """키와 스케일에 따른 구성음 반환"""
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

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

def analyze_audio(audio_file):
    # 오디오 로딩
    loader = es.MonoLoader(filename=audio_file, sampleRate=44100)
    audio = loader()

    print("\n=== 기본 음악 정보 ===")

    try:
        # 1. 키/스케일 분석
        key_extractor = es.KeyExtractor()
        key, scale, key_strength = key_extractor(audio)
        key_with_relative = get_relative_key(key, scale)
        scale_notes = get_scale_notes(key, scale)
        print(f"키: {key_with_relative}")
        print(f"구성음: {scale_notes}")
        # print(f"키 신뢰도: {key_strength:.2f}")
    except Exception as e:
        print("키 분석 실패:", str(e))

    try:
        # 2. 리듬/BPM 분석
        rhythm_extractor = es.RhythmExtractor2013()
        bpm, beats, beats_confidence, _, _ = rhythm_extractor(audio)
        print(f"\nBPM: {bpm:.1f}")
        # print(f"비트 신뢰도: {beats_confidence:.2f}")
    except Exception as e:
        print("리듬 분석 실패:", str(e))

    print("\n=== 음악 특성 분석 ===")

    # 프레임 파라미터 설정
    frame_size = 2048
    hop_size = 1024
    sample_rate = 44100

    # 알고리즘 초기화
    windowing = es.Windowing(type='hann', size=frame_size)
    spectrum = es.Spectrum()
    mfcc = es.MFCC(
        inputSize=frame_size//2 + 1,
        numberBands=40,
        numberCoefficients=13,
        sampleRate=sample_rate,
        lowFrequencyBound=20,
        highFrequencyBound=20000
    )
    rms = es.RMS()

    # 분석 결과 저장
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
    print(mfcc_mean, mfcc_std, mfcc_array)

    # 음색의 안정성 (낮을수록 안정적)
    timbre_stability = np.mean(mfcc_std[1:])

    # 음색의 밝기
    brightness = np.mean(mfcc_mean[1:6])

    # 음색의 복잡도
    complexity = np.sum(np.abs(mfcc_mean[6:]))


    # print(f"\n음색 안정성: {'높음' if timbre_stability < 20 else '보통' if timbre_stability < 40 else '낮음'}")
    print(f"\n음색 특성: {'밝은' if brightness > 0 else '어두운'} 음색")
    print(f"\n음색 복잡도: {'단순함' if complexity < 100 else '보통' if complexity < 200 else '복잡함'}")

    # 장르 추정
    possible_genres = []
    if timbre_stability < 20:
        if complexity < 100:
            possible_genres.append('클래식')
        elif complexity > 200:
            possible_genres.append('재즈')
        else:
            possible_genres.append('팝')
    elif timbre_stability > 40:
        if complexity > 150:
            possible_genres.append('록')
            possible_genres.append('재즈')
    else:
        if complexity > 180:
            possible_genres.append('일렉트로닉')
        else:
            possible_genres.append('팝')

    print(f"\n가능성 높은 장르: {', '.join(possible_genres)}")

def main():
    analyze_audio('test.mp3')

if __name__ == "__main__":
    main()