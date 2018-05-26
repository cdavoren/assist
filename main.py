#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, time, re, datetime, queue, html

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QDir, QThread, QMutex, pyqtSignal

import auslab

import numpy as np
import cv2

import keyboard
import yaml

AUSLAB_MINIMUM_WIDTH = 1008
AUSLAB_MINIMUM_HEIGHT = 730
AUSLAB_MINIMUM_BLACK = 80

PATIENT_NAME_REGEX = re.compile(r'Name:\s+(.*)DOB:')
PATIENT_UR_REGEX = re.compile(r'UR No:\s+[A-Z]{2}(\d{6})')
PATIENT_DOB_REGEX = re.compile(r'DOB:\s+(\d{2}-\w{3}-\d{2})')
COLL_REGEX = re.compile(r'Coll:\s+(\d{2}:\d{2}\s+\d{2}-\w{3}-\d{2})')

TEST_REGEX = {
    'Hb' : re.compile(r'Hgb\s+:\s+(\d+)\s+[ HLC]'),
    'WBC' : re.compile(r'[EW]BC\s+:\s+([0-9\.]+)\s+[ HLC]'),
    'Plt' : re.compile(r'PLT\s+:\s+(\d+)\s+[ HLC]'),
    'Na' : re.compile(r'Sodium\s+(\d+)\s+'),
    'K' : re.compile(r'Potassium\s+([0-9\.]+)\s+'),
    'Cr' : re.compile(r'Creatinine\s+(\<?\>?\s*\d+)\s+'),
    'Mg' : re.compile(r'Magnesium\s+([0-9\.]+)\s+'),
    'Ca' : re.compile(r'Corr Ca\s+([0-9\.]+)\s+'),
    'Ph' : re.compile(r'Phosphate\s+([0-9\.]+)\s+'),
    'eGFR' : re.compile(r'eGFR\s+(\<?\>?\s*\d+)\s+'),
}

useLongForm = False

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
        result_order = ['Hb', 'Plt', 'WBC', 'Na', 'K', 'eGFR', 'Cr', 'Mg', 'Ca', 'Ph']
        for result_name in result_order:
            if result_name in date_results.keys():
                output_string_columns.append(date_results[result_name])
            else:
                output_string_columns += '-'
        return '\t'.join(output_string_columns)

    def getPasteableTests(self, test_datetime, useLongForm):
        if test_datetime not in self.test_results.keys():
            return ''
        date_results = self.test_results[test_datetime]
        if not useLongForm:
            output_string_columns = []
            output_string_columns.append("{0}/{1}".format(date_results.get('Hb', '-'), date_results.get('Plt', '-')))
            output_string_columns.append("{0}".format(date_results.get('WBC', '-')))
            output_string_columns.append("{0}".format(date_results.get('Na', '-')))
            output_string_columns.append("{0}".format(date_results.get('K', '-')))
            output_string_columns.append("{0}/{1}".format(date_results.get('eGFR', '-'), date_results.get('Cr', '-')))
            return '\t'.join(output_string_columns)
        else:
            return "- Hb {0}, Plt {1}, WBC {2}\n- Na {3}, K {4}, Mg {5}\n- Ca {6}, Ph {7}\n- eGFR {8}, Cr {9}".format(
                date_results.get('Hb', '-'),
                date_results.get('Plt', '-'),
                date_results.get('WBC', '-'),
                date_results.get('Na', '-'),
                date_results.get('K', '-'),
                date_results.get('Mg', '-'),
                date_results.get('Ca', '-'),
                date_results.get('Ph', '-'),
                date_results.get('eGFR', '-'),
                date_results.get('Cr', '-'),
            )

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

class ProcessClipboardImageThread(QThread):
    log = pyqtSignal(str)
    message = pyqtSignal(str)

    def __init__(self, app):
        super().__init__()
        self.enabled = True
        self.app = app
        self.image_queue = self.app.image_queue
        self.image_queue_lock = self.app.image_queue_lock

    def run(self):
        self.log.emit('*** ProcessClipboardImageThread started ***')
        config = None
        with open('config.yaml', 'r') as config_file:
            config = yaml.load(config_file)

        # print(config)
        auslab_config = config['auslab']
        # print(auslab_config)
        recognizer = auslab.AuslabTemplateRecognizer(auslab_config)

        current_qimage = None

        while self.enabled:

            while current_qimage is None:
                self.image_queue_lock.lock()
                if self.image_queue.empty():
                    self.image_queue_lock.unlock()
                    time.sleep(10)
                else:
                    current_qimage = self.image_queue.get()
                    self.image_queue_lock.unlock()

            current_qimage = current_qimage.convertToFormat(QImage.Format_RGB32)
            im_width = current_qimage.width()
            im_height = current_qimage.height()

            # print(self.qimage.byteCount())
            ptr = current_qimage.bits()
            ptr.setsize(current_qimage.byteCount())
            im = np.array(ptr).reshape(im_height, im_width, 4)

            # Beware garbage collector...
            current_qimage = None

            # print(np.size(im))
            # print(np.shape(im))
            if im_width >= AUSLAB_MINIMUM_WIDTH and im_width < AUSLAB_MINIMUM_WIDTH + 20:
                if im_height >= AUSLAB_MINIMUM_HEIGHT and im_height < AUSLAB_MINIMUM_HEIGHT + 50:

                    image_grey = cv2.cvtColor(im, cv2.COLOR_RGBA2GRAY)
                    image_inverted = cv2.bitwise_not(image_grey)
                    _, image_thresh = cv2.threshold(image_inverted, 240, 255, 0)

                    # print(cv2.countNonZero(image_thresh))
                    black_count = cv2.countNonZero(image_thresh)
                    # print("Black count: {0}".format(black_count))
                    percentage = (black_count / (im_width * im_height)) * 100.0
                    # print("Percentage black: {0}".format(percentage))
                    if percentage >= AUSLAB_MINIMUM_BLACK:
                        self.log.emit("AUSLAB image identified.")

                        ai = auslab.AuslabImage(auslab_config)
                        ai.loadScreenshot(im)
                        header_lines = [recognizer.recognizeLine(x) for x in ai.getHeaderLines()]
                        center_lines = [recognizer.recognizeLine(x) for x in ai.getCenterLines()]

                        UR = PATIENT_UR_REGEX.search(header_lines[0]).group(1)
                        name = PATIENT_NAME_REGEX.search(header_lines[1]).group(1)
                        DOB = PATIENT_DOB_REGEX.search(header_lines[1]).group(1)
                        collection_time = COLL_REGEX.search(header_lines[0]).group(1)

                        self.log.emit('UR: {0}'.format(UR))
                        self.log.emit('Name: {0}'.format(name))
                        self.log.emit('DOB: {0}'.format(DOB))
                        self.log.emit('Collection time: {0}'.format(collection_time))
                        current_patient = add_patient(UR, name, DOB)

                        for line in header_lines:
                            self.log.emit(line)

                        for line in center_lines:
                            self.log.emit(line)
                            for tk,tr in TEST_REGEX.items():
                                try:
                                    result = tr.search(line)
                                    if result is None:
                                        continue
                                    result = tr.search(line).group(1)
                                    current_patient.add_test_result(collection_time, tk, result)
                                except IndexError:
                                    continue
                        self.log.emit(current_patient.getTabulatedTests(collection_time))
                        self.log.emit(current_patient.getPasteableTests(collection_time, self.app.useLongForm))
                        self.message.emit('AUSLAB image processed')
                        continue
            self.message.emit('Not an AUSLAB image')
            self.log.emit('Not an AUSLAB image.')

class Assist(QWidget):
    logsig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.useLongForm = False
        self.initUI()

    def initUI(self):
        self.mainIcon = QIcon('main.ico')
        self.setGeometry(100, 100, 500, 400)
        self.setWindowTitle('Assist')
        self.setWindowIcon(self.mainIcon)
        
        self.longCheckBox = QCheckBox("&Long form")
        self.longCheckBox.setCheckState(False)
        self.longCheckBox.toggled.connect(self.handleCheckBox)

        self.log_lock = QMutex()

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.longCheckBox)
        self.layout.addWidget(self.log)

        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setIcon(self.mainIcon)
        self.trayIcon.show()

        QApplication.clipboard().dataChanged.connect(self.handleClipboardChanged)

        self.image_queue = queue.Queue()
        self.image_queue_lock = QMutex()
        self.image_processing_thread = ProcessClipboardImageThread(self)
        self.image_processing_thread.message.connect(self.handleProcessMessage)
        self.image_processing_thread.log.connect(self.handleClipboardLog)
        self.image_processing_thread.start()

        self.show()

    def handleProcessMessage(self, message_str):
        self.logMessage('Message signal')
        self.trayIcon.showMessage('Assist', message_str, 3000)

    def handleClipboardLog(self, message):
        self.logMessage(message)

    def handleClipboardChanged(self):
        self.logMessage('Clipboard changed')
        qimage = QApplication.clipboard().image()
        if qimage.isNull():
            return
        self.image_queue_lock.lock()
        self.image_queue.put(qimage)
        self.image_queue_lock.unlock()

    def handleCheckBox(self, data):
        # print("Toggling checkbox...")
        self.logMessage('Toggling checkbox...')
        self.useLongForm = self.longCheckBox.isChecked()
        # print('  Long form: {0}'.format(useLongForm))

    def logMessage(self, message):
        self.log_lock.lock()
        dt = datetime.datetime.now()
        datestr = dt.strftime('%d-%m-%Y %H:%M:%S')
        self.log.insertHtml('<span style="color: #888888">[{0}]</span> {1}<br />'.format(datestr, html.escape(message)))
        self.log_lock.unlock()

def main():
    # print(sys.path)
    # ai = auslab.AuslabImage()
    keyboard.add_hotkey('ctrl+shift+a', print, args=('triggered', 'hotkey'))

    app = QApplication(sys.argv)
    QApplication.setApplicationName('Assist')
    assist = Assist()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
