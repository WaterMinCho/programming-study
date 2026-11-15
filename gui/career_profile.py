"""현재 사용자의 직무 추천 선택값만 기기 설정에 보관함."""
import json

from PyQt6.QtCore import QSettings
from session import valid_user
from career.recommend import ACTIVITIES, DEGREES, EXPERIENCES, INTERESTS, MAJORS, Education, Profile


class ProfileStorageError(ValueError):
    pass


def decode(raw):
    value = json.loads(raw)
    if (not isinstance(value, dict)
            or set(value) != {"version", "education", "experiences", "activities", "interests"}
            or type(value["version"]) is not int or value["version"] != 1):
        raise ValueError("지원하지 않는 추천 입력 형식")

    def choices(items, allowed, blank=False):
        if not isinstance(items, list) or any(
                not isinstance(item, str) or (item not in allowed and not (blank and item == ""))
                for item in items):
            raise ValueError("추천 입력 선택값 오류")
        return tuple(items)

    education = value["education"]
    if not isinstance(education, list):
        raise ValueError("학력 입력 형식 오류")
    rows = []
    for row in education:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("학력 입력 형식 오류")
        choices([row[0]], DEGREES, True)
        choices([row[1]], MAJORS, True)
        rows.append(Education(*row))
    activities = choices(value["activities"], ACTIVITIES)
    interests = choices(value["interests"], INTERESTS)
    if len(interests) > 3 or len(set(interests)) != len(interests) or len(set(activities)) != len(activities):
        raise ValueError("추천 입력 중복 또는 선택 수 오류")
    return Profile(tuple(rows), choices(value["experiences"], EXPERIENCES, True), activities, interests)


class ProfileStore:
    def __init__(self, settings, user):
        if not isinstance(user, str) or not valid_user(user):
            raise ValueError("추천 입력을 저장할 사용자를 확인해 주세요.")
        self.settings = settings
        self.key = "career/profile/" + user.casefold()

    def load(self):
        try:
            self.settings.sync()
            if self.settings.status() != QSettings.Status.NoError:
                raise ProfileStorageError("기기 설정을 읽지 못했습니다. 저장 공간과 설정 파일 권한을 확인해 주세요.")
            if not self.settings.contains(self.key):
                return Profile()
            raw = self.settings.value(self.key, type=str)
            return decode(raw)
        except ProfileStorageError:
            raise
        except (TypeError, ValueError):
            raise ProfileStorageError("저장한 입력을 읽지 못했습니다. [저장한 입력 삭제] 후 다시 입력해 주세요.") from None

    def save(self, profile):
        value = {"version": 1, "education": [[row.degree, row.major] for row in profile.education],
                 "experiences": list(profile.experiences), "activities": list(profile.activities),
                 "interests": list(profile.interests)}
        raw = json.dumps(value, ensure_ascii=False)
        decode(raw)
        if not any((profile.education, profile.experiences, profile.activities, profile.interests)):
            self.delete()
            return
        self._write(raw)

    def delete(self):
        self._write(None)

    def _write(self, raw):
        before = self.settings.value(self.key)
        if raw == before or (raw is None and before is None):
            return
        if raw is None:
            self.settings.remove(self.key)
        else:
            self.settings.setValue(self.key, raw)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            # 저장 실패 때 메모리 설정도 이전 값으로 되돌림. 원문은 오류 메시지에 넣지 않음.
            if before is None:
                self.settings.remove(self.key)
            else:
                self.settings.setValue(self.key, before)
            raise ProfileStorageError("기기 저장을 마치지 못했습니다. 변경한 내용이 남지 않을 수 있습니다. 저장 공간과 설정 파일 권한을 확인해 주세요.")
