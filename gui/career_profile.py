"""현재 사용자의 직무 추천 선택값만 기기 설정에 보관함."""
import json

from PyQt6.QtCore import QSettings
from session import valid_user
import career.recommend as recommendation
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
        self.result_key = "career/recommendation/" + user.casefold()

    def _open(self):
        # status()가 이전 오류를 유지하므로 작업마다 같은 저장 위치를 새로 읽음.
        base = self.settings
        # 이미 파싱한 잘못된 INI 내용은 새 핸들에도 공유됨. 손상 판정은 덮어쓰지 않음.
        if base.property("careerProfileFormatError") or base.status() == QSettings.Status.FormatError:
            raise ProfileStorageError("기기 설정 파일을 읽지 못했습니다. 설정 파일을 확인한 뒤 프로그램을 다시 실행해 주세요.")
        if base.organizationName():
            settings = QSettings(base.format(), base.scope(), base.organizationName(), base.applicationName())
        else:
            settings = QSettings(base.fileName(), base.format())
        settings.setFallbacksEnabled(False)
        settings.sync()
        if settings.status() == QSettings.Status.FormatError:
            base.setProperty("careerProfileFormatError", True)
        if settings.status() != QSettings.Status.NoError:
            raise ProfileStorageError("기기 설정을 읽지 못했습니다. 저장 공간과 설정 파일 권한을 확인해 주세요.")
        return settings

    def load(self):
        try:
            settings = self._open()
            if not settings.contains(self.key):
                return Profile()
            raw = settings.value(self.key, type=str)
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
        try:
            decode(raw)
        except (TypeError, ValueError):
            raise ProfileStorageError("저장할 입력의 형식을 확인하지 못했습니다. 항목을 다시 선택해 주세요.") from None
        if not any((profile.education, profile.experiences, profile.activities, profile.interests)):
            self.delete()
            return
        self._write(raw)

    def delete(self):
        self._write(None)

    def _result_value(self, profile, catalog, results):
        return {"input_fingerprint": recommendation.profile_fingerprint(profile),
                "rules_version": recommendation.VERSION,
                "catalog_fingerprint": recommendation.catalog_fingerprint(catalog),
                "role_ids": [row.role_id for row in results]}

    def save_result(self, profile, catalog, results):
        """추천받기를 눌렀을 때 현재 사용자의 별도 키에 결과를 저장함."""
        settings = self._open()
        try:
            saved = decode(settings.value(self.key, type=str)) if settings.contains(self.key) else Profile()
        except (TypeError, ValueError):
            raise ProfileStorageError("저장한 입력을 확인하지 못했습니다. 입력을 다시 저장해 주세요.") from None
        if saved != profile:
            raise ProfileStorageError("입력을 저장한 뒤 다시 [추천받기]를 눌러주세요.")
        expected = recommendation.recommend(profile, catalog, include_experience_only=True)
        if tuple(results) != expected:
            raise ProfileStorageError("추천 기준이 바뀌었습니다. 다시 [추천받기]를 눌러주세요.")
        raw = json.dumps(self._result_value(profile, catalog, expected), ensure_ascii=False)
        self._write_values(settings, {self.result_key: raw})

    def load_result(self, profile, catalog):
        """입력·기준·결과를 대조하고 손상되거나 낡은 결과만 폐기함."""
        settings = self._open()
        if not settings.contains(self.result_key):
            return None
        expected = recommendation.recommend(profile, catalog, include_experience_only=True)
        try:
            value = json.loads(settings.value(self.result_key, type=str))
        except (TypeError, ValueError, RecursionError):
            value = None
        if value != self._result_value(profile, catalog, expected):
            self._write_values(settings, {self.result_key: None})
            return None
        return expected

    def _write(self, raw):
        settings = self._open()
        if raw is not None and raw == settings.value(self.key):
            return
        self._write_values(settings, {self.key: raw, self.result_key: None})

    def _write_values(self, settings, values):
        before = {key: settings.value(key) for key in values}
        if values == before:
            return
        for key, value in values.items():
            if value is None:
                settings.remove(key)
            else:
                settings.setValue(key, value)
        settings.sync()
        if settings.status() != QSettings.Status.NoError:
            # 저장 실패 때 메모리 설정도 이전 값으로 되돌림. 원문은 오류 메시지에 넣지 않음.
            for key, value in before.items():
                if value is None:
                    settings.remove(key)
                else:
                    settings.setValue(key, value)
            raise ProfileStorageError("기기 저장을 마치지 못했습니다. 변경한 내용이 남지 않을 수 있습니다. 저장 공간과 설정 파일 권한을 확인해 주세요.")
