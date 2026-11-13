# -*- coding: utf-8 -*-
"""기존 import 경로를 유지함. 구현은 learning_data.submission에 둠."""
import sys

from learning_data import submission as _implementation

sys.modules[__name__] = _implementation
