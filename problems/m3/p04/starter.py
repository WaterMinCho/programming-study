def candies(groups, team, index):
    try:
        sizes = groups[team]
        size = sizes[index]
        return 120 // size
    except ____:
        return "팀 없음"
    except ____:
        return "조 없음"
    except ____:
        return "인원 0명"
