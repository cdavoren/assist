import cv2

from .auslab import AuslabImage
from .auslab import AuslabImageLine
from .auslab import AuslabTemplateRecognizer

from .auslab import AUSLAB_SCREENSHOT_Y_BORDER_MAX
from .auslab import AUSLAB_SCREENSHOT_X_BORDER_MAX

# AUSLAB_HEADER_X_START = 56
# AUSLAB_HEADER_Y_START = 74

# AUSLAB_HEADER_X_END = 979
# AUSLAB_HEADER_Y_END = 156

# AUSLAB_HEADER_CHAR_NUM = 77
# AUSLAB_HEADER_LINE_NUM = 3

# AUSLAB_LINE_SPACING = 7

# AUSLAB_LINE_HEIGHT = 23
# AUSLAB_CHAR_WIDTH = 12

# AUSLAB_CONDENSED_LINE_HEIGHT = 23
# AUSLAB_CONDENSED_CHAR_WIDTH = 8

# AUSLAB_CENTRAL_PANEL_Y_START = 194
# AUSLAB_CENTRAL_PANEL_Y_END = 668

# AUSLAB_F1_NORMAL = cv2.cvtColor(cv2.imread('F1_normal.png'), cv2.COLOR_BGR2GRAY)
# AUSLAB_F1_CONDENSED = cv2.cvtColor(cv2.imread('F1_condensed.png'), cv2.COLOR_BGR2GRAY)

__all__ = ['auslab.AuslabImage']
