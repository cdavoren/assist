#!/usr/bin/env python
#-*- coding: utf-8 -*-

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

class DarkStyle(QProxyStyle):

    def styleBase(self, style=None):
        if style is None:
            DarkStyle.base = QStyleFactory.create("Fusion")
        else:
            DarkStyle.base = style
        return DarkStyle.base

    def __init__(self, style=None):
        if style is not None:
            QProxyStyle(style)
        self.styleBase()
        super().__init__()

    def polish(self, obj):
        if isinstance(obj, QPalette):
            # print("Called with QPalette...")
            obj.setColor(QPalette.Window, QColor(53, 53, 53))
            obj.setColor(QPalette.WindowText, Qt.white);
            obj.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127));
            obj.setColor(QPalette.Base, QColor(42, 42, 42));
            obj.setColor(QPalette.AlternateBase, QColor(66, 66, 66));
            obj.setColor(QPalette.ToolTipBase, Qt.white);
            obj.setColor(QPalette.ToolTipText, QColor(53, 53, 53));
            obj.setColor(QPalette.Text, Qt.white);
            obj.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127));
            obj.setColor(QPalette.Dark, QColor(35, 35, 35));
            obj.setColor(QPalette.Shadow, QColor(20, 20, 20));
            obj.setColor(QPalette.Button, QColor(53, 53, 53));
            obj.setColor(QPalette.ButtonText, Qt.white);
            obj.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127));
            obj.setColor(QPalette.BrightText, Qt.red);
            obj.setColor(QPalette.Link, QColor(42, 130, 218));
            obj.setColor(QPalette.Highlight, QColor(42, 130, 218));
            obj.setColor(QPalette.Disabled, QPalette.Highlight, QColor(80, 80, 80));
            obj.setColor(QPalette.HighlightedText, Qt.white);
            obj.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(127, 127, 127));
            return obj
        elif isinstance(obj, QApplication):
            # print("Called with QApplication...")
            defaultFont = QApplication.font()
            # defaultFont.setPointSize(defaultFont.pointSize() + 1)
            obj.setFont(defaultFont)

            stylesheetFile = open('darkstyle/darkstyle.qss')
            stylesheet = ''
            for line in stylesheetFile:
                stylesheet += line
            stylesheetFile.close()

            obj.setStyleSheet(stylesheet)

        else:
            pass

