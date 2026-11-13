# 실제 풀이 자료 받기와 샘플 추출

<a id="실제-자료를-받아-샘플로-확인합니다"></a>

[스터디 개발 시작](STUDY_START.md) · [fork에서 PR 보내기](LEARNING_WORKFLOW.md) · [입력 항목 설명](LEARNING_STARTER.md)

WaterMinCho가 준비한 **같은 실제 자료 묶음을 비공개로 받아 각자 샘플링·테스트합니다.** 서버 계정이나 관리용 인증 키는 필요하지 않습니다. 모델 코드는 본인 fork에서 개발하고 공통 프로젝트에 PR로 보냅니다.

<a id="자료를-받아-저장소-밖에-풉니다"></a>

## 비공개 자료 받기와 압축을 풀 위치

스터디에 등록한 Google 계정으로 Drive를 엽니다. 노트북과 자료 파일은 서로 다른 폴더에 있습니다.

- **Colab에서 처음 실습할 때**는 **3.학습추천모델** 폴더의 `01_Colab에서_풀이_샘플_열기.ipynb`를 열고 **파일 → Drive에 사본 저장**을 누릅니다. 기본값 `source = "synthetic"`으로 셀을 위에서부터 실행하면 고정한 커밋 `cc87ec96`의 코드로 버전 5 합성 자료를 만들고 학습 구간의 첫 8건을 읽습니다. 여기까지는 CPU로 충분합니다.
- **실제 파이썬 샘플**은 **ROKEY 모델 스터디 · 공통 학습 자료** 폴더에서 `python-train-s8-seed42.json`을 내려받습니다. 본인 PC에서 확인하려면 아래 [샘플 읽기](#샘플에서-모델-입력과-정답-읽기)의 경로에 저장하세요. Colab으로 실습할 때는 ‘풀이 샘플 열기’ 셀을 `source = "file"`, `track = "python"`으로 바꾸고 받은 JSON을 고르세요. 이때 파일을 Colab에 업로드합니다. 노트북은 지정한 과목의 버전 4·5 학습용 샘플을 받습니다. 한 사람이 같은 문제를 다시 풀면 같은 문항도 여러 기록에 나올 수 있습니다.
- **직접 샘플을 뽑을 때**는 **ROKEY 모델 스터디 · 공통 학습 자료** 폴더에서 `common-input-f4-20261112.zip`을 받습니다. 아래 설명에 따라 압축을 풀고 필요한 수만큼 고를 수 있습니다.

담당 이슈에는 자료를 열었는지만 적습니다. 실제 파일·다운로드 주소·개별 풀이 결과는 개인 작업 공간에 보관합니다. ZIP의 SHA-256은 [공통 자료 안내](LEARNING_STARTER.md#세-팀원이-사용할-자료-버전을-맞춥니다)에 있습니다. Windows 터미널에서는 `certutil -hashfile ZIP파일경로 SHA256`, Mac에서는 `shasum -a 256 ZIP파일경로`로 확인합니다. 경로에 공백이 있으면 큰따옴표로 감쌉니다.

본인 fork를 받은 폴더 옆에 `study-data/common-input-f4-20261112` 폴더를 만듭니다. Windows에서는 ZIP을 오른쪽 클릭해 압축 풀기 메뉴를 열고 **대상 폴더를 방금 만든 `common-input-f4-20261112`로 지정**합니다. ZIP 안에는 `synthetic`과 `recorded-python`이 바로 들어 있습니다. `study-data`에 바로 풀면 아래 명령의 경로와 달라집니다.

Mac 터미널에서는 `programming-study` 폴더에서 아래처럼 풉니다. `ZIP파일경로`는 받은 ZIP을 터미널로 끌어다 놓아 입력해도 됩니다.

```sh
unzip ZIP파일경로 -d ../study-data/common-input-f4-20261112
```

```text
model-study/
  programming-study/                 본인 fork · 코드와 설명을 커밋합니다
  study-data/                        비공개 · Git에 올리지 않습니다
    common-input-f4-20261112/
      recorded-python/manifest.json  실제 파이썬 자료
      synthetic/manifest.json        파이썬·AI 가상 자료
    samples/                         직접 뽑은 입력 확인용 샘플
```

| 자료 | 학습 train | 검증 validation | 평가 test |
|---|---|---|---|
| 실제 파이썬 | 84건 | 29건 | 18건 |
| 합성 파이썬 | 8건 | 2건 | 2건 |
| 합성 AI | 8건 | 2건 | 2건 |

현재 실제 자료는 한 사람의 파이썬 기록 131건입니다. 학습 84건 중 48건은 예측 전에 공개된 과거 이력이 없습니다. 빈 이력 처리 실습에도 사용하며 나중에 알게 된 결과로 빈칸을 채우지 않습니다. 실제 AI 학습 자료는 이 묶음에 없습니다. AI 기록을 서버에 보관한 것과 모델 입력으로 준비한 것은 구분합니다. 실제 자료로 입력을 읽어보는 실습은 가능하지만 새 학습자에 대한 성능이나 추천 효과를 판단할 규모는 아닙니다.

<a id="받은-파일을-확인합니다"></a>

## 자료 파일 검증 명령과 정상 결과

`programming-study` 폴더에서 터미널을 엽니다. SourceTree를 쓰는 사람도 Python 명령은 이 터미널에서 실행합니다. 추가 라이브러리나 GPU는 필요하지 않습니다.

```sh
python -m learning_server.sample check --dataset ../study-data/common-input-f4-20261112/recorded-python
```

`status`가 `verified`, `source`가 `recorded`, `synthetic`이 `false`이고 위 표의 행 수가 나오면 실제 파이썬 자료를 읽은 것입니다. 도구는 학습·검증·평가 파일과 번호표의 해시를 모두 확인합니다. 파일 내용이나 개별 풀이 번호는 출력하지 않습니다.

`python`을 찾지 못하면 Windows는 `py`, Mac은 `python3`로 바꿉니다. `No module named learning_server`가 나오면 현재 폴더에 `learning_server`가 있는지 확인합니다. `manifest.json`을 찾지 못하면 한 단계 더 들어가 `recorded-python`을 지정했는지 확인합니다.

<a id="학습-구간에서-8건을-뽑습니다"></a>

## 학습 구간에서 샘플 8건 뽑기

```sh
python -m learning_server.sample sample --dataset ../study-data/common-input-f4-20261112/recorded-python --track python --split train --size 8 --seed 42 --length 32 --out ../study-data/samples/python-train-s8-seed42.json
```

학습 구간에서 예시 8건을 뽑고 예시마다 최근 풀이 이력을 최대 32개로 맞춥니다. 난수 시드인 `42`를 같은 값으로 지정하면 같은 자료에서 같은 샘플을 뽑습니다. 원래 학습·검증·평가 구분과 학습 자료로 만든 번호표는 유지합니다.

`status: input_checked`, `target_separation: passed`, `padding: passed`를 확인합니다. 이번 정답을 바꿔도 입력이 같고 실제 풀이와 빈 자리를 구분하는지 확인한 결과입니다. `shapes`에는 예시 수와 이력·개념 배열의 크기가 나옵니다. 난이도 항목의 크기는 검사에 사용한 샘플 수와 이력 길이로 표시합니다. `empty_histories`는 이력이 없는 예시 수, `truncated_histories`는 지정한 길이에 맞춰 이력을 자른 예시 수입니다. 모델의 예측·학습·성능을 검사한 결과는 아닙니다.

샘플은 `--out`에 지정한 비공개 JSON 파일로 저장합니다. 이미 있는 파일은 덮어쓰지 않으며 저장소 안에는 만들지 않습니다. 다시 뽑을 때는 새 파일 이름을 지정합니다. 8건보다 적은 구간에서는 `--size`를 줄입니다.

<a id="본인-코드에서-입력과-정답을-나눕니다"></a>

## 샘플에서 모델 입력과 정답 읽기

저장한 파일은 아래처럼 읽습니다. `programming-study` 폴더에서 실행합니다.

```python
import json
from pathlib import Path

path = Path("../study-data/samples/python-train-s8-seed42.json")
sample = json.loads(path.read_text(encoding="utf-8"))
inputs = sample["batch"]["inputs"]
targets = sample["batch"]["targets"]
vocabulary = sample["vocabulary"]
print("예시 수:", len(targets))
print("이력 너비:", len(inputs["questions"][0]))
```

공유 폴더의 버전 4 샘플에는 난이도 항목이 없습니다. 현재 도구로 같은 묶음에서 다시 뽑으면 난이도와 확인 여부 네 항목도 들어가며, 기록이 없는 값은 `0`과 `False`입니다.

`inputs`만 모델에 전달하고 `targets`는 예측 오차를 계산할 때 사용합니다. 예전 오답의 0과 빈 자리의 0은 `mask`로 구분합니다. 각 모델에서 사용할 항목은 [담당별 미션](LEARNING_MISSIONS.md)을 따릅니다. 배열을 텐서로 바꾸고 실제 모델에 통과시키는 코드는 각자 작성합니다.

AI 과목은 아래 명령으로 합성 자료에서 4건을 뽑습니다. 결과는 별도 파일에 저장하고 합성 자료로 실행했다고 적습니다.

```sh
python -m learning_server.sample sample --dataset ../study-data/common-input-f4-20261112/synthetic --track ai --split train --size 4 --seed 42 --length 32 --out ../study-data/samples/ai-train-s4-seed42.json
```

<a id="모델-학습과-평가를-이어갑니다"></a>

## 샘플 테스트 후 전체 자료로 학습·평가하기

8건 샘플로 파일 읽기와 작은 예측부터 확인합니다. 모델 비교에는 원래 학습 구간 전체를 사용하고 검증 구간으로 설정을 고릅니다. 마지막 평가 구간은 최종 비교에 사용합니다. 구간을 섞어 다시 나누거나 샘플만으로 번호표를 새로 만들지 않습니다. 전체 자료를 읽는 코드는 [공통 입력 예제](LEARNING_STARTER.md#세-모델의-공통-입력-형식)에 있습니다.

PR에는 코드·테스트·실행 방법과 실제 확인한 범위를 남깁니다. 예를 들면 “공통 입력 버전 4의 실제 파이썬 자료에서 train 8건, 시드 42, 이력 길이 32로 입력 확인을 통과했음. 모델 학습은 미실행임”처럼 적습니다. 자료 수신·입력 확인·모델 학습을 각각 구분합니다.

실제 기록·샘플 JSON·번호표·개별 예측·실제 자료로 학습한 가중치는 비공개로 보관합니다. 공개 PR에는 합성 자료로 재현하는 테스트를 넣습니다. 실제 자료의 상세 결과는 WaterMinCho에게 비공개로 전달합니다. [실험 기록 양식](LEARNING_EXPERIMENT_TEMPLATE.md)에 사용한 버전과 샘플 설정을 남겨 두면 같은 조건으로 다시 확인할 수 있습니다.
