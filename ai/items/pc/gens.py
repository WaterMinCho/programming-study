"""상황별 코드의 CNN 공간 크기와 이미지 하나의 특징 수를 생성함."""
from aiprep.gen import blank, gen


@gen("pc-g01", unit="18f", level=2, tags=["CNN 모양"],
     ref=["11차시 노트북 02 [65]", "16차시 노트북 01 [8]"],
     facts=["F18-38", "F18-39"], step="18f/4", basis="lecture-formula", family="cnn-flatten-size")
def cnn_features(r):
    """공간을 유지하는 합성곱과 절반으로 줄이는 풀링 두 묶음 뒤 특징 수를 계산함."""
    side = r.pick([8, 12, 16, 20])
    channels = r.pick([4, 8])
    batch = r.pick([1, 2, 3])
    width = side
    for _ in range(2):
        width = (width + 2 - 3) // 1 + 1
        width = (width - 2) // 2 + 1
    features = channels * width * width
    return blank(
        stem=f"입력은 float32[{batch}, 1, {side}, {side}]입니다. kernel_size=3, padding=1, stride=1인 합성곱 뒤에 kernel_size=2, stride=2인 최대 풀링을 적용하고 같은 묶음을 한 번 더 적용합니다. 합성곱의 dilation과 groups는 1, 풀링의 padding은 0, dilation은 1, ceil_mode는 False입니다. 마지막 채널은 {channels}개입니다. 배치 축을 남겨 펼칠 때 한 이미지의 특징 수는 ____ 개입니다.",
        blanks=[{"answer": [str(features)], "mode": "number", "unit": "개"}],
        explain=f"공간 한 변은 {side}에서 {width}로 줄어듭니다. 한 이미지의 채널·높이·너비를 곱하면 {channels}×{width}×{width}={features}개입니다. 배치 크기 {batch}는 곱하지 않습니다.",
        params={"side": side, "channels": channels, "batch": batch})
