#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, os, time, re, datetime, queue, html, sqlite3, configparser, codecs

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QObject, QDir, QThread, QMutex, pyqtSignal, Qt

from darkstyle import DarkStyle
from logoview import RCLogoView

import auslab

import numpy as np
import cv2

import keyboard
import yaml

from peewee import *

# START EXCERPT - From https://stackoverflow.com/questions/4020539/process-escape-sequences-in-a-string-in-python
ESCAPE_SEQUENCE_RE = re.compile(r'''
    ( \\U........      # 8-digit hex escapes
    | \\u....          # 4-digit hex escapes
    | \\x..            # 2-digit hex escapes
    | \\[0-7]{1,3}     # Octal escapes
    | \\N\{[^}]+\}     # Unicode characters by name
    | \\[\\'"abfnrtv]  # Single-character escapes
    )''', re.UNICODE | re.VERBOSE)

def decode_escapes(s):
    def decode_match(match):
        return codecs.decode(match.group(0), 'unicode-escape')

    return ESCAPE_SEQUENCE_RE.sub(decode_match, s)
# END EXCERPT

AUSLAB_MINIMUM_WIDTH = 1008
AUSLAB_MINIMUM_HEIGHT = 730
AUSLAB_MINIMUM_BLACK = 80

PATIENT_NAME_REGEX = re.compile(r'Name:\s+(.*)DOB:')
PATIENT_UR_REGEX = re.compile(r'UR No:\s+[A-Z]{2,3}(\d{6})')
PATIENT_DOB_REGEX = re.compile(r'DOB:\s+(\d{2}-\w{3}-\d{2})')
LAB_NO_REGEX = re.compile(r'Lab No:\s+([0-9\-]+)')
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
    'CRP' : re.compile(r'CRP\s+(\<?[0-9\.]+)'),
    'AST' : re.compile(r'AST\s+(\d+)'),
    'ALT' : re.compile(r'ALT\s+(\d+)'),
    'GGT' : re.compile(r'Gamma GT\s+(\d+)'),
    'ALP' : re.compile(r'ALP\s+(\d+)'),
    'LD' : re.compile(r'LD\s+(\d+)'),
    'INR' : re.compile(r'INR\s+([0-9\.]+)'),
    'ESR' : re.compile(r'ESR\s+(\d+)'),
    'Neut' : re.compile(r'Neut.*?:\s+([0-9\.]+)'),
    'Lymph' : re.compile(r'Lymph.*?:\s+([0-9\.]+)'),
    'Mono' : re.compile(r'Mono.*?:\s+([0-9\.]+)'),
    'Eosin' : re.compile(r'Eosin.*?:\s+([0-9\.]+)'),
    'Baso' : re.compile(r'Baso.*?:\s+([0-9\.]+)'),
}

database_proxy = Proxy()

class Configuration:

    instance = None

    def __init__(self, config_filename):
        self.config = yaml.load(config_filename)

    @staticmethod
    def current():
        if Configuration.instance is None:
            Configuration.instance = Configuration(open('config.yaml', 'r'))
        return Configuration.instance.config

class BaseModel(Model):
    class Meta:
        database = database_proxy
        
class Patient(BaseModel):
    UR = CharField()
    name = CharField()
    DOB = CharField()

    def add_test_result(self, lab_number, test_datetime, test_name, result):
        # And overwrite
        lab_test_group = None

        try:
            lab_test_group = self.lab_test_groups.select().where(LabTestGroup.lab_number == lab_number).get()
        except LabTestGroup.DoesNotExist:
            lab_test_group = LabTestGroup(patient=self, lab_number=lab_number, datetime=test_datetime)
            lab_test_group.save()

        try:
            lab_test = lab_test_group.lab_tests.select().where(LabTest.name == test_name).get()
            lab_test.value = result
            lab_test.save()
            return
        except LabTest.DoesNotExist:
            lab_test = LabTest(lab_test_group=lab_test_group, name=test_name, value=result)
            lab_test.save()


    def getPasteableTests(self, lab_number, format_string):
        lab_test_group = None
        try:
            lab_test_group = self.lab_test_groups.select().where(LabTestGroup.lab_number == lab_number).get()
        except LabTestGroup.DoesNotExist:
            # print('No lab results exist for the given lab number {}'.format(lab_number))
            return ''

        lab_tests = {}
        for lab_test in lab_test_group.lab_tests:
            lab_tests[lab_test.name] = lab_test.value

        output_string = decode_escapes(format_string).format(
            hb=lab_tests.get('Hb', '-'),
            platelets=lab_tests.get('Plt', '-'),
            wbc=lab_tests.get('WBC', '-'),
            sodium=lab_tests.get('Na', '-'),
            potassium=lab_tests.get('K', '-'),
            magnesium=lab_tests.get('Mg', '-'),
            calcium=lab_tests.get('Ca', '-'),
            phosphate=lab_tests.get('Ph', '-'),
            egfr=lab_tests.get('eGFR', '-'),
            creatinine=lab_tests.get('Cr', '-'),
            ast=lab_tests.get('AST', '-'),
            alt=lab_tests.get('ALT', '-'),
            ggt=lab_tests.get('GGT', '-'),
            alp=lab_tests.get('ALP', '-'),
            ldh=lab_tests.get('LD', '-'),
            crp=lab_tests.get('CRP', '-'),
            esr=lab_tests.get('ESR', '-'),
            inr=lab_tests.get('INR', '-'),
            neut=lab_tests.get('Neut', '-'),
            lymph=lab_tests.get('Lymph', '-'),
            mono=lab_tests.get('Mono', '-'),
            eosin=lab_tests.get('Eosin', '-'),
            baso=lab_tests.get('Baso', '-'),
            t="\t",
            tab="\t",
            n="\n"
        )
        return output_string

class LabTestGroup(BaseModel):
    patient = ForeignKeyField(Patient, backref='lab_test_groups')
    lab_number = CharField()
    datetime = CharField()

class LabTest(BaseModel):
    lab_test_group = ForeignKeyField(LabTestGroup, backref='lab_tests')
    name = CharField()
    value = CharField()

class PatientDatabase(QObject):
    log = pyqtSignal(str)

    def __init__(self, db_path):
        super().__init__()
        self.patients = {}
        self.db_path = db_path
        self.db = SqliteDatabase(db_path)
        database_proxy.initialize(self.db)
        self.db.create_tables([Patient, LabTestGroup, LabTest])
        self.db_lock = QMutex()

    def save(self):
        self.db_lock.lock()
        for UR, patient in self.patients.items():
            self.log.emit('Patient: {0}'.format(UR))
        self.db_lock.unlock()

    def add_patient(self, UR, name, DOB):
        self.db_lock.lock()
        patient = None
        try:
            patient = Patient.get(Patient.UR == UR)
            self.log.emit('Patient exist {}'.format(UR))
        except Patient.DoesNotExist:
            patient = Patient(UR=UR, name=name, DOB=DOB)
            self.log.emit('Patient did not exist {}'.format(UR))
        patient.save()
        self.patients[UR] = patient
        self.db_lock.unlock()
        return patient

class ProcessClipboardImageThread(QThread):
    log = pyqtSignal(str)
    message = pyqtSignal(str)
    processing = pyqtSignal(str)
    clipboard = pyqtSignal(str)

    def __init__(self, assist_widget, config):
        super().__init__()
        self.enabled = True
        self.assist_widget = assist_widget
        self.image_queue = self.assist_widget.image_queue
        self.image_queue_lock = self.assist_widget.image_queue_lock
        self.patient_db = PatientDatabase(Configuration.current()['main']['database_path'])
        self.patient_db.log.connect(self.logMessage)
        self.last_UR = None
        self.config = config

    def logMessage(self, message_str):
        self.log.emit(message_str)

    def processingStart(self):
        self.processing.emit('start')

    def processingStop(self):
        self.processing.emit('stop')

    def pasteLastUR(self):
        clipboard_data = QApplication.clipboard().text()
        if clipboard_data is not None and len(clipboard_data) == 6 and clipboard_data.isdigit():
            self.log.emit('Pasting clipboard data...')
            keyboard.write(clipboard_data)
        elif self.last_UR is not None:
            self.log.emit('Pasting last UR...')
            keyboard.write(self.last_UR)

    def run(self):
        def not_auslab_image_message():
            self.message.emit('Not an AUSLAB image')
            self.log.emit('Not an AUSLAB image.')

        self.log.emit('*** ProcessClipboardImageThread started ***')
        keyboard.add_hotkey('ctrl+shift+x', self.pasteLastUR)

        auslab_config = Configuration.current()['auslab']
        recognizer = auslab.AuslabTemplateRecognizer(auslab_config)

        current_qimage = None

        while self.enabled:
            while current_qimage is None:
                self.image_queue_lock.lock()
                if self.image_queue.empty():
                    self.image_queue_lock.unlock()
                    time.sleep(0.5)
                else:
                    current_qimage = self.image_queue.get()
                    self.image_queue_lock.unlock()

            self.log.emit('Converting image format...')
            current_qimage = current_qimage.convertToFormat(QImage.Format_RGB32)
            im_width = current_qimage.width()
            im_height = current_qimage.height()

            # print(self.qimage.byteCount())
            ptr = current_qimage.bits()
            ptr.setsize(current_qimage.byteCount())
            im = np.array(ptr).reshape(im_height, im_width, 4)

            # Beware garbage collector...
            current_qimage = None

            if im_width >= AUSLAB_MINIMUM_WIDTH and im_width < AUSLAB_MINIMUM_WIDTH + 20 and im_height >= AUSLAB_MINIMUM_HEIGHT and im_height < AUSLAB_MINIMUM_HEIGHT + 50:
                self.log.emit('Converting to greyscale...')
                image_grey = cv2.cvtColor(im, cv2.COLOR_RGBA2GRAY)
                self.log.emit('Inverting image...')
                image_inverted = cv2.bitwise_not(image_grey)
                self.log.emit('Thresholding image...')
                _, image_thresh = cv2.threshold(image_inverted, 240, 255, 0)

                self.log.emit('Counting black pixels...')
                black_count = cv2.countNonZero(image_thresh)
                percentage = (black_count / (im_width * im_height)) * 100.0
                if percentage >= AUSLAB_MINIMUM_BLACK:
                    self.processingStart()
                    self.log.emit("AUSLAB image identified.")

                    ai = auslab.AuslabImage(auslab_config)
                    ai.loadScreenshot(im)
                    header_lines = [recognizer.recognizeLine(x) for x in ai.getHeaderLines()]
                    center_lines = [recognizer.recognizeLine(x) for x in ai.getCenterLines()]

                    UR = PATIENT_UR_REGEX.search(header_lines[0]).group(1)
                    name = PATIENT_NAME_REGEX.search(header_lines[1]).group(1)
                    DOB = PATIENT_DOB_REGEX.search(header_lines[1]).group(1)
                    collection_time = COLL_REGEX.search(header_lines[0]).group(1)
                    lab_number = LAB_NO_REGEX.search(header_lines[0]).group(1)
                    self.last_UR = UR

                    self.log.emit('UR: {0}'.format(UR))
                    self.log.emit('Name: {0}'.format(name))
                    self.log.emit('DOB: {0}'.format(DOB))
                    self.log.emit('Collection time: {0}'.format(collection_time))
                    self.log.emit('Lab No: {0}'.format(lab_number))
                    
                    current_patient = self.patient_db.add_patient(UR, name, DOB)

                    for line in header_lines:
                        self.log.emit(line)

                    for line in center_lines:
                        self.log.emit(line)
                        for tk,tr in TEST_REGEX.items():
                            try:
                                result = tr.search(line)
                                if result is None:
                                    continue # to next line
                                result_match = result.group(1)
                                current_patient.add_test_result(lab_number, collection_time, tk, result_match)
                            except IndexError:
                                continue # to next line
                    clipboard_data = current_patient.getPasteableTests(lab_number, self.assist_widget.getCurrentOutputString())
                    self.log.emit(clipboard_data)
                    self.clipboard.emit(clipboard_data)
                    self.message.emit('AUSLAB image processed')
                    self.processingStop()
                else:
                    not_auslab_image_message()
            else:
                not_auslab_image_message()

class Assist(QWidget):
    logsig = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.useLongForm = False
        self.config = config
        self.initUI()

    def initUI(self):
        self.mainIcon = QIcon('main-grey.ico')
        self.setGeometry(100, 100, 1000, 500)
        self.setWindowTitle('Assist')
        self.setWindowIcon(self.mainIcon)

        self.processingLogo = RCLogoView()

        self.longCheckBox = QCheckBox("&Long form")
        self.longCheckBox.setCheckState(False)
        self.longCheckBox.toggled.connect(self.handleCheckBox)

        self.formatComboBox = QComboBox()
        self.formatComboBox.addItems([x['name'] for x in self.config['main']['output_strings']])
        self.formatComboBox.currentIndexChanged.connect(self.handleOutputStringChanged)
        # self.formatComboBox.setStyleSheet('QComboBox { color: red; }')

        self.formatText = QTextEdit()
        self.formatText.setReadOnly(True)
        self.formatText.document().setDefaultStyleSheet('span.sv { color: #CC44FF; }')

        self.handleOutputStringChanged()
        
        self.log_lock = QMutex()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.document().setDefaultStyleSheet('* { font-family: Consolas; } span.logmessage { color: #FFFFFF; white-space: pre; }')

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.processingLogo)
        # self.layout.addWidget(self.longCheckBox)
        self.layout.addWidget(self.formatComboBox)
        self.layout.addWidget(self.formatText)
        self.layout.addWidget(self.log)

        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setIcon(self.mainIcon)
        self.trayIcon.show()

        QApplication.clipboard().dataChanged.connect(self.handleClipboardChanged)

        self.image_queue = queue.Queue()
        self.image_queue_lock = QMutex()

        self.image_processing_thread = ProcessClipboardImageThread(self, self.config)
        self.image_processing_thread.message.connect(self.handleProcessThreadMessage)
        self.image_processing_thread.log.connect(self.handleLogMessage)
        self.image_processing_thread.clipboard.connect(self.handleClipboardMessage)
        self.image_processing_thread.processing.connect(self.handleProcessingStateChange)
        self.image_processing_thread.start()

        self.show()

    def getCurrentOutputString(self):
        output_string = [x["string"] for x in self.config["main"]["output_strings"] if x["name"] == self.formatComboBox.currentText()]
        if len(output_string) > 0:
            output_string = output_string[0]
            return output_string
        else:
            return None

    def handleOutputStringChanged(self):
        def highlightOutputString(output_string):
            return re.sub(r'\{(.*?)\}', r'<span class="sv">{\1}</span>', output_string)

        output_string = self.getCurrentOutputString()
        if output_string is None:
            output_string = ''
        output_string = output_string.replace('\\n', '\n')
        output_string = output_string.replace('\n', '<br />')
        output_html = highlightOutputString(output_string)
        # print(output_html)
        self.formatText.setHtml(output_html)

    def handleProcessingStateChange(self, message_str):
        if message_str == 'start':
            self.processingLogo.animationStart()
        elif message_str == 'stop':
            self.processingLogo.animationStop()

    def handleProcessThreadMessage(self, message_str):
        self.logMessage('Message signal')
        self.trayIcon.showMessage('Assist', message_str, 3000)

    def handleLogMessage(self, message):
        self.logMessage(message)

    def handleClipboardChanged(self):
        self.logMessage('Clipboard changed')
        qimage = QApplication.clipboard().image()
        if qimage.isNull():
            return
        self.image_queue_lock.lock()
        self.image_queue.put(qimage)
        self.image_queue_lock.unlock()
        self.logMessage('Image waiting in queue...')

    def handleCheckBox(self, data):
        # print("Toggling checkbox...")
        self.logMessage('Toggling checkbox...')
        self.useLongForm = self.longCheckBox.isChecked()
        # print('  Long form: {0}'.format(useLongForm))

    def logMessage(self, message):
        self.log_lock.lock()
        dt = datetime.datetime.now()
        datestr = dt.strftime('%d-%m-%Y %H:%M:%S')
        self.log.insertHtml('<span style=""><span style="color: #888888;">[{0}]</span> <span class="logmessage">{1}</span></span><br />'.format(datestr, html.escape(message)))
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        self.log_lock.unlock()

    def handleClipboardMessage(self, content):
        cp = QApplication.clipboard()
        cp.setText(content, cp.Clipboard)

    def closeEvent(self, event):
        self.trayIcon.hide()

    def bringFocus(self):
        current_flags = self.windowFlags()
        self.setWindowFlags(current_flags | Qt.WindowStaysOnTopHint)
        # self.activateWindow()
        # self.windowHandle().requestActivate()
        self.show()
        self.setWindowFlags(current_flags)
        self.show()

def bringFocus(assist):
    print("Bring focus called...")
    assist.bringFocus()

def main():
    config = Configuration.current()
    # print(config)
    db_path = config['main']['database_path']

    app = QApplication(sys.argv)
    app.setApplicationName('Assist')
    app.setStyle(DarkStyle())
    assist = Assist(config)
    # keyboard.add_hotkey('ctrl+shift+a', bringFocus, args=(assist,))
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
