#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, time, re, datetime
import win32clipboard as w32clip
import pywintypes
import yaml

import auslab

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QDir, QThread, pyqtSignal

from PIL import ImageGrab

import numpy
import numpy.core
import numpy.core.multiarray

AUSLAB_MINIMUM_WIDTH = 1008
AUSLAB_MINIMUM_HEIGHT = 730
AUSLAB_MINIMUM_BLACK = 80


PATIENT_NAME_REGEX = re.compile(r'Name:\s+(.*)DOB:')
PATIENT_UR_REGEX = re.compile(r'UR No:\s+[A-Z]{2}(\d{6})')
PATIENT_DOB_REGEX = re.compile(r'DOB:\s+(\d{2}-\w{3}-\d{2})')
COLL_REGEX = re.compile(r'Coll:\s+(\d{2}:\d{2}\s+\d{2}-\w{3}-\d{2})')

TEST_REGEX = {
    'Hb' : re.compile(r'Hgb\s+:\s+(\d+)\s+[ HL]'),
    'WBC' : re.compile(r'[EW]BC\s+:\s+([0-9\.]+)\s+[ HL]'),
    'Plt' : re.compile(r'PLT\s+:\s+(\d+)\s+[ HL]'),
    'Na' : re.compile(r'Sodium\s+(\d+)\s+'),
    'K' : re.compile(r'Potassium\s+([0-9\.]+)\s+'),
    'Cr' : re.compile(r'Creatinine\s+(\<?\>?\s*\d+)\s+'),
    'eGFR' : re.compile(r'eGFR\s+(\<?\>?\s*\d+)\s+'),
}

class Patient:

    def __init__(self):
        self.name = None
        self.UR = None
        self.DOB = None
        self.test_results = {}

    def add_test_result(self, test_datetime, test_name, result):
        if test_datetime not in self.test_results.keys():
            self.test_results[test_datetime] = {}
        self.test_results[test_datetime][test_name] = result

    def getTabulatedTests(self, test_datetime):
        if test_datetime not in self.test_results.keys():
            return ''
        output_string_columns = [test_datetime]
        date_results = self.test_results[test_datetime]
        result_order = ['Hb', 'Plt', 'WBC', 'Na', 'K', 'eGFR', 'Cr']
        for result_name in result_order:
            if result_name in date_results.keys():
                output_string_columns.append(date_results[result_name])
            else:
                output_string_columns += '-'
        return '\t'.join(output_string_columns)

    def getPasteableTests(self, test_datetime):
        if test_datetime not in self.test_results.keys():
            return ''
        date_results = self.test_results[test_datetime]
        output_string_columns = []
        output_string_columns.append("{0}/{1}".format(date_results.get('Hb', '-'), date_results.get('Plt', '-')))
        output_string_columns.append("{0}".format(date_results.get('WBC', '-')))
        output_string_columns.append("{0}".format(date_results.get('Na', '-')))
        output_string_columns.append("{0}".format(date_results.get('K', '-')))
        output_string_columns.append("{0}/{1}".format(date_results.get('eGFR', '-'), date_results.get('Cr', '-')))
        return '\t'.join(output_string_columns)

class PatientTest:

    def __init__(self):
        self.datetime = None
        self.key = None
        self.value = None

patients = {}

def add_patient(UR, name, DOB):
    if UR in patients.keys():
        return patients[UR]
    else:
        patient = Patient()
        patient.UR = UR
        patient.name = name
        patient.DOB = DOB
        patients[UR] = patient
        return patient

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
                time.sleep(0.01)
                continue

    def run(self):
        config = None
        with open('config.yaml', 'r') as config_file:
            config = yaml.load(config_file)

        print(config)
        auslab_config = config['auslab']
        print(auslab_config)

        self.openClipboard()
        lastSequenceNumber = w32clip.GetClipboardSequenceNumber()
        w32clip.CloseClipboard()
        recognizer = auslab.AuslabTemplateRecognizer(auslab_config)
        test_re = {}
        for key,regex in TEST_REGEX.items():
            test_re[key] = re.compile(regex)
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
                        print("Black count: {0}".format(black_count))
                        percentage = (black_count / (im_width * im_height)) * 100.0
                        print("Percentage black: {0}".format(percentage))
                        if percentage >= AUSLAB_MINIMUM_BLACK:
                            print("AUSLAB image identified.")
                            self.openClipboard()

                            ai = auslab.AuslabImage(auslab_config)
                            ai.loadScreenshotFromPIL(im)
                            header_lines = [recognizer.recognizeLine(x) for x in ai.getHeaderLines()]
                            center_lines = [recognizer.recognizeLine(x) for x in ai.getCenterLines()]

                            UR = PATIENT_UR_REGEX.search(header_lines[0]).group(1)
                            name = PATIENT_NAME_REGEX.search(header_lines[1]).group(1)
                            DOB = PATIENT_DOB_REGEX.search(header_lines[1]).group(1)
                            collection_time = COLL_REGEX.search(header_lines[0]).group(1)

                            print('UR: {0}'.format(UR))
                            print('Name: {0}'.format(name))
                            print('DOB: {0}'.format(DOB))
                            print('Collection time: {0}'.format(collection_time))
                            current_patient = add_patient(UR, name, DOB)

                            for line in header_lines:
                                print(line)

                            for line in center_lines:
                                print(line)
                                for tk,tr in TEST_REGEX.items():
                                    try:
                                        result = tr.search(line)
                                        if result is None:
                                            continue
                                        result = tr.search(line).group(1)
                                        current_patient.add_test_result(collection_time, tk, result)
                                    except IndexError:
                                        continue
                            print(current_patient.getTabulatedTests(collection_time))

                            # for l in header_lines + center_lines:
                                # print("'{0}'".format(l))

                            w32clip.EmptyClipboard()
                            w32clip.SetClipboardData(w32clip.CF_UNICODETEXT, current_patient.getPasteableTests(collection_time))
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
    # print(sys.path)
    # ai = auslab.AuslabImage()
    app = QApplication(sys.argv)
    assist = Assist()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
