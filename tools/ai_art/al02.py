"""필터와 기하학적 변환을 수치 예로 그린 그림임."""
from tools.ai_art.application_vision import register, register_levels

register(globals(), 2, {
    'a': ['mean', 'median', 'kernel'],
    'b': ['erode', 'dilate', 'morph'],
    'c': ['resize', 'interpolate', 'maskresize'],
    'd': ['translate', 'inverse', 'rotate'],
    'e': ['corners', 'divide', 'bridge'],
})

register_levels(globals(), {'a2a': 2, 'a2c': 3, 'a2e': 3})
