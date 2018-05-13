#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, time
import win32clipboard as w32clip
import pywintypes

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QDir, QThread, pyqtSignal

from PIL import ImageGrab

AUSLAB_MINIMUM_WIDTH = 1008
AUSLAB_MINIMUM_HEIGHT = 730
AUSLAB_MINIMUM_BLACK = 80

class ClipboardThread(QThread):
    dataSent = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

    def openClipboard(self):
        running = True
        while running:
            try:
                w32clip.OpenClipboard()
                running = False
            except pywintypes.error:
                continue

    def run(self):
        self.openClipboard()
        lastSequenceNumber = w32clip.GetClipboardSequenceNumber()
        w32clip.CloseClipboard()
        while True:
            time.sleep(0.25)
            self.openClipboard()
            sequenceNumber = w32clip.GetClipboardSequenceNumber()
            if sequenceNumber == lastSequenceNumber:
                w32clip.CloseClipboard()
                continue

            lastSequenceNumber = sequenceNumber

            if w32clip.IsClipboardFormatAvailable(w32clip.CF_BITMAP):
                im = ImageGrab.grabclipboard()
                # Check to see if it's an AUSLAB image
                im_width = im.size[0]
                im_height = im.size[1]
                if im_width >= AUSLAB_MINIMUM_WIDTH and im_width < AUSLAB_MINIMUM_WIDTH + 20:
                    if im_height >= AUSLAB_MINIMUM_HEIGHT and im_height < AUSLAB_MINIMUM_HEIGHT + 50:
                        black_count = 0
                        for i in range(im_width):
                            for j in range(im_height):
                                if im.getpixel((i, j)) == (0,0,0):
                                    black_count += 1
                        print("Black count: {0}", black_count)
                        percentage = (black_count / (im_width * im_height)) * 100.0
                        print("Percentage black: {0}".format(percentage))
                        if percentage >= AUSLAB_MINIMUM_BLACK:
                            print("AUSLAB image identified.")
                            w32clip.OpenClipboard()
                            w32clip.EmptyClipboard()
                            w32clip.SetClipboardData(w32clip.CF_UNICODETEXT, "Bitmap: {0} x {1}".format(im.size[0], im.size[1]))
                            w32clip.CloseClipboard()

                self.dataSent.emit({'message' : 'Bitmap became available: {0}, {1}'.format(im.size[0], im.size[1])})
            else:
                self.dataSent.emit({'message' : 'Bitmap became unavailable.'})
                w32clip.CloseClipboard()


class Assist(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()

        self._clipThread = ClipboardThread()
        self._clipThread.dataSent.connect(self.handleClipboardEvent)
        self._clipThread.start()

    def initUI(self):
        print("*** initUI ***")
        self.setGeometry(300, 300, 300, 220)
        self.setWindowTitle('Assist')
        
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.log)

        self.show()

    def handleClipboardEvent(self, data):
        self.log.appendPlainText('Clipboard event: {0}'.format(data['message']))

def main():
    app = QApplication(sys.argv)
    assist = Assist()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
