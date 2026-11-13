"""프레임 처리와 경계·직선·영역의 위치를 그린 예임."""
from tools.ai_art.application_vision import register, register_levels
from tools.ai_art.course03_followup import (
    binary_values, local_thresholds, global_histogram, contour_modes,
    corner_windows, quality_and_distance, circle_radius, missing_detection,
)

register(globals(), 3, {
    'a': ['frames', 'read', 'fps', 'release'],
    'b': ['difference', 'sobel', 'gradients'],
    'c': ['canny', 'nms', 'hysteresis'],
    'd': ['votes', 'normal', 'hough'],
    'e': ['roi', 'centroid', 'offset'],
})

register_levels(globals(), {'a3a': 4, 'a3b': 3, 'a3e': 4})
