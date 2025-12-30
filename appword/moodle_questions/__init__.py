# Cho phép import tất cả class từ moodle_questions

# -*- coding: utf-8 -*-

from .MoodleQuiz import MoodleQuiz
from .ChoiceTFQuestion import ChoiceTFQuestion
from .MultiChoiceQuestion import MultiChoiceQuestion
from .ShortAnswerQuestion import ShortAnswerQuestion

__all__ = [
    "MoodleQuiz",
    "ChoiceTFQuestion",
    "MultiChoiceQuestion",
    "ShortAnswerQuestion",
]


# from .calculatedmulti import *
# from .cloze import *
# from .ddmarker import *
# from .ddwtos import *
# from .essay import *
# from .gapselect import *
# from .matching import *
# from .truefalse import *
# from .numerical import *
# from .ordering import *
# from .ShortAnswerQuestion import *

