# -*- coding: utf-8 -*-
"""기존 import 경로를 유지함. 구현은 learning_data.sync_schedule에 둠."""
import sys

from learning_data import sync_schedule as _implementation

sys.modules[__name__] = _implementation
