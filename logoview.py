#!/usr/bin/env python
#-*- coding: utf-8 -*-

import math
from PyQt5 import QtGui, QtCore, QtWidgets

class RCLogoView(QtWidgets.QGraphicsView):
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.image = QtGui.QImage('rc-logo.png')
        self.pixmap = QtGui.QPixmap.fromImage(self.image)

        self.imageWidth = 100

        self.margin = 30

        greaterCentroidRadius = self.imageWidth / math.sqrt(3)

        self.actualWidth = round(greaterCentroidRadius * 2) + self.margin

        self.scene = QtWidgets.QGraphicsScene(self)
        self.item = QtWidgets.QGraphicsPixmapItem(self.pixmap)
        self.scene.addItem(self.item)
        self.setScene(self.scene)

        self.setMinimumSize(self.actualWidth, self.actualWidth)

        self.setMaximumHeight(self.actualWidth)

        self.animation = QtCore.QVariantAnimation(self, startValue=0.0, endValue=360.0, duration=1250, valueChanged=self.on_valueChanged)

        self.animation.setLoopCount(-1)

        self.setStyleSheet('background-color: transparent; border-style: none;')

    def resetRotation(self):
        self.item.setRotation(0)
        self.item.update()

    def animationStart(self):
        self.animation.start()

    def animationStop(self):
        self.animation.stop()
        self.resetRotation()

    @QtCore.pyqtSlot(QtCore.QVariant)
    def on_valueChanged(self, value):
        self.item.setTransformOriginPoint(self.imageWidth / 2, self.imageWidth / 2)
        self.item.setRotation(value)
        self.item.update()

