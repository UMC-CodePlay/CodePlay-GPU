import os
from src.config import logger


def replace_spaces_in_filename(file_path):
    """
    파일 이름에 있는 띄어쓰기를 밑줄(_)로 변경한 후,
    변경된 파일의 전체 경로(new_file_path)를 반환합니다.
    file_path는 디렉토리가 아니라 개별 파일(예: .mp3)이어야 합니다.
    """
    # 파일 존재 여부 및 파일인지 확인
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"파일 '{file_path}'가 존재하지 않습니다.")
    if not os.path.isfile(file_path):
        raise ValueError(f"'{file_path}'는 파일이 아닙니다.")

    directory, filename = os.path.split(file_path)

    # 파일 이름에 띄어쓰기가 있는 경우에만 변경 진행
    if " " in filename:
        new_filename = filename.replace(" ", "_")
        new_file_path = os.path.join(directory, new_filename)
        try:
            os.rename(file_path, new_file_path)
            logger.info(f"[FILE] 파일 이름 변경에 성공했습니다.[{file_path}] -> [{new_file_path}")
            return new_file_path
        except Exception as e:
            logger.info(f"[FILE ERROR] 파일 이름 변경에 실패했습니다: {e}")
            return file_path
    else:
        return file_path
