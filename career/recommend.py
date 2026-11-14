"""선택한 관심·활동·경력·전공을 직무 과제와 대조함. 저장과 통신은 수행하지 않음."""
from dataclasses import dataclass

VERSION = "2026-11-15-v1"
DEGREES = {"associate": "전문학사", "bachelor": "학사", "master": "석사", "doctor": "박사", "other": "그 외 과정"}
MAJORS = {
    "computing": "컴퓨터·소프트웨어", "electronics": "전기·전자·통신", "mechanical": "기계·자동차·로봇",
    "math": "수학·통계", "science": "자연과학", "industrial": "산업공학·물류", "design": "디자인·예술",
    "business": "경영·경제", "humanities": "인문·사회", "education": "교육", "health": "보건·의료",
    "other": "그 밖의 전공·분류하기 어려움",
}
EXPERIENCES = {
    "frontend": "웹·앱 화면 개발", "backend": "서버·서비스 개발", "data": "데이터 분석·관리",
    "ml": "AI·머신러닝", "embedded": "임베디드·펌웨어", "robot": "로봇·자동화",
    "infra": "인프라·IT 운영", "qa": "소프트웨어 테스트·품질", "mechanical": "기계 설계·정비",
    "electrical": "전기·전자 설계·정비", "production": "생산·공정·품질 관리", "logistics": "물류·운송",
    "design": "디자인·콘텐츠 제작", "planning": "서비스·사업 기획", "sales": "영업·고객 지원",
    "administration": "사무·회계·인사", "education": "교육·강의", "research": "연구·실험",
    "health": "보건·의료 서비스", "construction": "건설·현장 관리", "other": "그 밖의 경력·분류하기 어려움",
}
ACTIVITIES = {
    "ui": "화면·사용 흐름 설계", "web": "웹·앱 화면 구현", "api": "API·서버 기능 구현",
    "data": "자료 정리·SQL·엑셀 분석", "automation": "반복 업무 자동화", "ml": "모델 학습·비교 실험",
    "image": "이미지·영상 처리", "hardware": "기계·회로·센서 다루기", "control": "장치 제어·통신 구현",
    "spatial": "지도·좌표·경로 다루기", "simulation": "수식·시뮬레이션 실험", "ops": "서버·네트워크 운영",
    "troubleshoot": "현장 문제 진단·복구", "test": "시험 조건 설계·결과 비교",
    "requirements": "사용자 요구 정리", "document": "작업 절차·교육 자료 작성",
}
# 관심은 직무 이름 대신 만들 결과로 질문하고 관련 과제를 가진 직무에 연결함.
INTERESTS = {
    "interaction": ("쓰기 편한 화면", "frontend"), "service": ("안정적인 서비스", "backend"),
    "data": ("쓸 수 있는 데이터", "data_engineering"), "perception": ("영상을 이해하는 모델", "robot_vision"),
    "movement": ("정확히 움직이는 로봇", "robot_control"), "autonomy": ("스스로 판단하는 로봇", "robot_navigation"),
    "reliability": ("고장에 강한 시스템", "platform_infrastructure"), "field": ("현장에서 작동하는 제품", "field_integration"),
}


@dataclass(frozen=True)
class Education:
    degree: str
    major: str


@dataclass(frozen=True)
class Profile:
    education: tuple[Education, ...] = ()
    experiences: tuple[str, ...] = ()
    activities: tuple[str, ...] = ()
    interests: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rule:
    interests: tuple[str, ...]
    activities: tuple[str, ...]
    experiences: tuple[str, ...]
    majors: tuple[str, ...]
    first_step: str


# 직접 근거는 roles.json의 tasks와 roadmap_nodes임. 학력·직무명으로 숙련을 판정하지 않음.
RULES = {
    "robot_control": Rule(("movement", "field"), ("hardware", "control", "simulation"),
        ("embedded", "robot", "mechanical", "electrical"), ("mechanical", "electronics"),
        "목표 각도와 센서 값을 그린 뒤, 오차가 커지는 구간을 찾아보세요."),
    "robot_navigation": Rule(("autonomy", "movement"), ("spatial", "hardware", "simulation"),
        ("robot", "embedded", "logistics"), ("mechanical", "electronics", "math"),
        "작은 격자 지도에 장애물을 놓고 목적지까지의 경로를 그려보세요."),
    "robot_vision": Rule(("perception", "autonomy"), ("image", "ml", "data"),
        ("ml", "data", "research"), ("computing", "math", "science"),
        "이미지 분류 예제에서 틀린 사진을 모아 어떤 조건에서 실패하는지 비교해보세요."),
    "field_integration": Rule(("field", "reliability"), ("troubleshoot", "hardware", "document"),
        ("robot", "production", "logistics", "mechanical", "electrical", "construction"),
        ("mechanical", "electronics", "industrial"),
        "장치가 응답하지 않는 상황을 정하고 전원·통신·로그의 확인 순서를 적어보세요."),
    "robot_policy": Rule(("autonomy", "movement"), ("simulation", "ml", "control"),
        ("ml", "research", "robot"), ("computing", "math", "mechanical"),
        "같은 시작 조건에서 두 행동 규칙을 실행하고 목표 도달 여부를 비교해보세요."),
    "robot_backend": Rule(("service", "data", "field"), ("api", "data", "control", "ops"),
        ("backend", "robot", "data", "infra"), ("computing", "electronics"),
        "로봇 상태 예시를 저장하고 마지막 상태를 조회하는 작은 API를 만들어보세요."),
    "platform_infrastructure": Rule(("service", "reliability"), ("ops", "automation", "troubleshoot"),
        ("infra", "backend"), ("computing", "electronics"),
        "작은 서비스를 실행하고 종료·재시작 때 로그와 응답이 어떻게 달라지는지 확인해보세요."),
    "frontend": Rule(("interaction", "service"), ("ui", "web", "requirements"),
        ("frontend", "design", "planning"), ("computing", "design"),
        "조회 중·결과 없음·오류가 난 상태를 구분하는 화면을 만들어보세요."),
    "backend": Rule(("service", "data"), ("api", "data", "requirements"),
        ("backend",), ("computing",),
        "입력을 검사하고 자료를 저장·조회하는 작은 API를 만들어보세요."),
    "data_engineering": Rule(("data", "reliability"), ("data", "automation", "ops"),
        ("data", "backend"), ("computing", "math", "industrial"),
        "중복·누락이 있는 CSV를 정리하고 다시 실행해도 같은 결과가 나오는지 확인해보세요."),
    "qa": Rule(("interaction", "reliability", "field"), ("test", "requirements", "document", "troubleshoot"),
        ("qa", "production"), ("computing", "industrial"),
        "입력 조건 하나를 정하고 정상·경계·오류 사례의 기대 결과를 적어보세요."),
}


@dataclass(frozen=True)
class Recommendation:
    role_id: str
    strength: tuple[int, int, int, int]
    interests: tuple[str, ...]
    activities: tuple[str, ...]
    experiences: tuple[str, ...]
    education: tuple[Education, ...]
    first_step: str


def recommend(profile, catalog):
    """관심·활동 근거가 있을 때만 추천하며 동률을 잘라내지 않음."""
    interests = set(profile.interests) & INTERESTS.keys()
    activities = set(profile.activities) & ACTIVITIES.keys()
    if not interests and not activities:
        return ()
    experiences = set(profile.experiences) & EXPERIENCES.keys()
    education = {row for row in profile.education if row.degree in DEGREES and row.major in MAJORS}
    results = []
    for role in catalog.roles:
        rule = RULES.get(role["id"])
        if rule is None:
            continue
        picked = tuple(key for key in rule.interests if key in interests)
        done = tuple(key for key in rule.activities if key in activities)
        if not picked and not done:
            continue
        work = tuple(key for key in rule.experiences if key in experiences)
        study = tuple(sorted((row for row in education if row.major in rule.majors),
                             key=lambda row: (row.major, row.degree)))
        # 범주별 근거 수를 대조함. 학위의 높이·행 수·경력 연수는 가산하지 않음.
        strength = (len(picked), len(done), len(work), len({row.major for row in study}))
        results.append(Recommendation(role["id"], strength, picked, done, work, study, rule.first_step))
    return tuple(sorted(results, key=lambda row: (tuple(-n for n in row.strength), row.role_id)))


def first_group(results, limit=3):
    """기본 개수의 경계와 같은 근거를 가진 직무도 함께 반환함."""
    if len(results) <= limit:
        return results
    edge = results[limit - 1].strength
    return tuple(row for row in results if row.strength >= edge)
