"""공개 지문의 조건으로 계산한 답을 생성기의 입력 이름에 연결함."""
import math
from fractions import Fraction

def g01_padding(original_length, max_length):
    """앞쪽을 최대 길이로 자른 뒤 추가할 PAD 수를 계산함."""
    return max(0, max_length - original_length)

def g02_embedding(vocab_size, vector_size, query, input_shape=None):
    """요청한 weight 원소 수 또는 유효 정수 번호 입력의 출력 모양을 계산함."""
    if query == "weights":
        return vocab_size * vector_size
    if query == "output" and input_shape is not None:
        return tuple(input_shape) + (vector_size,)
    raise ValueError("요청과 출력 모양에 필요한 입력 모양을 명시해야 함")

def g03_lstm_parameters(input_size, hidden_size, bidirectional):
    """1층, bias True, proj_size 0인 LSTM의 두 bias 벡터까지 계산함."""
    if type(bidirectional) is not bool:
        raise ValueError("양방향 여부를 명시해야 함")
    directions = 2 if bidirectional else 1
    return directions * 4 * hidden_size * (input_size + hidden_size + 2)

def g04_tfidf(document_count, document_frequency, term_frequency):
    """주어진 ln(N/(DF+1)) 식에 TF를 곱하고 마지막에 소수 넷째 자리로 표시함."""
    value = term_frequency * math.log(document_count / (document_frequency + 1))
    return format(value, ".4f")


def i17_g01(p):
    return [str(g01_padding(p['length'],p['limit']))]


def i17_g02(p):
    return [str(g02_embedding(p['v'],p['d'],'weights' if p['form']=='weight' else 'output',(p['b'],p['t'])))]


def i17_g03(p):
    return [str(g03_lstm_parameters(p['i'],p['h'],p['bi']))]


def i17_g04(p):
    return [str(g04_tfidf(p['n'],p['df'],p['tf']))]



def i17_g05(p):
    tp = int(p["tp"])
    tn = int(p["tn"])
    fp = int(p["fp"])
    fn = int(p["fn"])
    form = p["form"]
    if form == "accuracy":
        num = tp + tn
        den = tp + tn + fp + fn
    elif form == "f1":
        num = 2 * tp
        den = 2 * tp + fp + fn
    else:
        raise ValueError("form must be accuracy or f1")
    if den == 0:
        raise ZeroDivisionError("denominator is zero")
    v = Fraction(num, den)
    sign = "-" if v < 0 else ""
    v = abs(v)
    q, r = divmod(v.numerator * 10000, v.denominator)
    if 2 * r >= v.denominator:
        q += 1
    return [f"{sign}{q // 10000}.{q % 10000:04d}"]


def _positive_integer(value, name):
    """양의 정수 조건을 확인함."""
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name}은 양의 정수여야 함.")
    return value


def _boolean(value, name):
    """불리언 조건을 확인함."""
    if type(value) is not bool:
        raise ValueError(f"{name}은 참 또는 거짓이어야 함.")
    return value


def i17_g06(params):
    """projection이 없는 LSTM 반환값의 모양·배치 축·연결 축을 계산함."""
    batch = _positive_integer(params["batch"], "batch")
    length = _positive_integer(params["length"], "length")
    _positive_integer(params["input_size"], "input_size")
    hidden = _positive_integer(params["hidden_size"], "hidden_size")
    layers = _positive_integer(params["layers"], "layers")
    bidirectional = _boolean(params["bidirectional"], "bidirectional")
    if params.get("batch_first", True) is not True:
        raise ValueError("공개 조건은 batch_first=True임.")
    if params.get("proj_size", 0) != 0:
        raise ValueError("공개 조건은 proj_size=0임.")
    directions = 2 if bidirectional else 1
    readout = params["readout"]
    if readout == "output":
        shape, batch_axis = [batch, length, directions * hidden], 0
    elif readout in ("h_n", "c_n"):
        shape, batch_axis = [layers * directions, batch, hidden], 1
    elif readout == "last":
        shape, batch_axis = [batch, directions * hidden], 0
    else:
        raise ValueError("공개 조건에 없는 반환값임.")
    ask = params["ask"]
    if ask == "concat_axis":
        if readout != "last" or not bidirectional:
            raise ValueError("연결 축 질문은 양방향 last에만 적용함.")
        # [B, H]의 마지막 축은 1과 -1로 지정할 수 있음.
        # 빈칸 순서 배열을 유지하며 대표 답 1을 반환함. -1도 같은 정답임.
        return ["1"]
    if ask == "shape":
        return [str(shape)]
    if ask == "batch_axis":
        return [str(batch_axis)]
    raise ValueError("공개 조건에 없는 질문 종류임.")
