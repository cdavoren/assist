#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, os, time, re, datetime, queue, html, sqlite3, configparser, codecs

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QObject, QDir, QThread, QMutex, pyqtSignal, Qt, QSize, pyqtSlot, QFile, QTextStream

from darkstyle import DarkStyle
from logoview import RCLogoView

import auslab

import numpy as np
import cv2

import keyboard
import yaml

from peewee import *

# import breeze_resources

import qdarkstyle

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

AUSLAB_MINIMUM_WIDTH_LARGE = 1258
AUSLAB_MINIMUM_HEIGHT_LARGE = 910

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
        self.config = yaml.safe_load(config_filename)

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
    processing = pyqtSignal(str, int, int)
    clipboard = pyqtSignal(str)
    lines_complete = pyqtSignal()

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
        self.auslab_image = None

    def logMessage(self, message_str):
        self.log.emit(message_str)

    def processingStart(self):
        self.processing.emit('start', -1, -1)

    def processingStop(self):
        self.processing.emit('stop', -1, -1)

    def processingUpdate(self, step, total_steps):
        self.processing.emit('update', step, total_steps)

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
            self.processingStart()
            current_qimage = current_qimage.convertToFormat(QImage.Format_RGB32)

            ai = auslab.AuslabImage(auslab_config)
            ai.loadScreenshot(current_qimage)

            self.auslab_image = ai

            recognizer = None
            if ai.size == ai.AUSLAB_SIZE_LARGE:
                recognizer = auslab.AuslabTemplateRecognizer(auslab_config['large'])
            elif ai.size == ai.AUSLAB_SIZE_NORMAL:
                recognizer = auslab.AuslabTemplateRecognizer(auslab_config['normal'])
            else:
                # TODO: USE EXCEPTIONS
                print('[Critical Errror] Unknown image size, cannot instantiate recognizer')
                not_auslab_image_message()
                current_qimage = None
                self.processingStop()
                continue
                # sys.exit(1)

            if ai.valid:
                self.log.emit("AUSLAB image identified.")

                # ai.getHeaderLines()
                # ai.getCenterLines()

                ## self.lines_complete.emit()

                raw_header_lines = ai.getHeaderLines()
                raw_center_lines = ai.getCenterLines()

                header_lines = []
                center_lines = []


                total_lines = len(raw_header_lines) + len(raw_center_lines)

                for i, raw_header_line in enumerate(raw_header_lines):
                    header_lines.append(recognizer.recognizeLine(raw_header_line))
                    self.processing.emit('update', i+1, total_lines)

                for i, raw_center_line in enumerate(raw_center_lines):
                    center_lines.append(recognizer.recognizeLine(raw_center_line))
                    self.processing.emit('update', i+1+len(raw_header_lines), total_lines)

                # header_lines = [recognizer.recognizeLine(x) for x in ai.getHeaderLines()]
                # center_lines = [recognizer.recognizeLine(x) for x in ai.getCenterLines()]

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

                # clipboard_data = 'There is no pasteable data'
                self.log.emit(clipboard_data)
                self.clipboard.emit(clipboard_data)
                self.message.emit('AUSLAB image processed')
                self.processingStop()
            else:
                not_auslab_image_message()
                self.processingStop()

            current_qimage = None

class Assist(QWidget):
    # logsig = pyqtSignal(str)

    WAITING_MESSAGE = 'AWAITING IMAGE - TAKE SCREENSHOT USING ALT+PRINTSCREEN'

    VERSION_FILENAME = 'version-number.txt'

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.initUI()

    def initUI(self):
        self.mainIcon = QIcon('AssistIcon.ico')
        self.setGeometry(100, 100, 1000, 500)
        self.setWindowTitle('Assist')
        self.setWindowIcon(self.mainIcon)

        self.processingLogo = RCLogoView()

        version_number = ''
        with open(self.VERSION_FILENAME) as f:
            version_number = f.readline()

        output_string_names = [x['name'] for x in self.config['main']['output_strings']]
        self.formatComboBox = QComboBox()
        self.formatComboBox.addItems(output_string_names)
        default_output_string = self.config['main']['default_output_string']
        if default_output_string in output_string_names:
            self.formatComboBox.setCurrentIndex(output_string_names.index(default_output_string))
        self.formatComboBox.currentIndexChanged.connect(self.handleOutputStringChanged)


        self.formatText = QTextEdit()
        self.formatText.setReadOnly(True)
        self.formatText.document().setDefaultStyleSheet('span.sv { color: #CC44FF; }')

        self.handleOutputStringChanged()
        
        self.log_lock = QMutex()
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.document().setDefaultStyleSheet('* { font-family: Consolas; } span.logmessage { color: #FFFFFF; white-space: pre; }')

        self.layout = QVBoxLayout(self)
        # self.layout.addWidget(self.processingLogo)

        self.statusWidget = QWidget(self)
        self.statusWidget.setObjectName('statusWidget')
        # self.statusWidget.setStyleSheet('font-family: "Arame Mono"; ')
        self.statusWidget.setStyleSheet('* { font-family: "Arame Mono"; font-size: 14px; } #statusWidget { border: none; }')
        self.statusLayout = QHBoxLayout(self.statusWidget)
        self.statusLayout.setContentsMargins(3, 3, 3, 3)
        self.statusLayout.addStretch()
        self.statusInitialLabel = QLabel('STATUS:')
        self.statusInitialLabel.setStyleSheet('color: #AAAAAA;')
        self.statusLayout.addWidget(self.statusInitialLabel)
        self.statusMessageLabel = QLabel(self.WAITING_MESSAGE)
        self.statusLayout.addWidget(self.statusMessageLabel)
        self.statusLayout.addStretch()
        self.layout.addWidget(self.statusWidget)

        self.repeatButton = QPushButton('&Re-copy last text', self)
        # self.repeatButton.setFlat(True)
        self.repeatButton.setStyleSheet('min-height: 30px; max-width: 100px;')
        self.repeatButton.clicked.connect(self.handleRepeatButtonClicked)

        self.versionLabel = QLabel(version_number)
        self.versionLabel.setStyleSheet('font-size: 10px;')
        self.versionLabel.setAlignment(Qt.AlignRight)

        self.layout.addWidget(QLabel('Output format:'))
        self.layout.addWidget(self.formatComboBox)
        self.layout.addWidget(self.formatText)
        self.layout.addWidget(QLabel('Debug log:'))
        self.layout.addWidget(self.log)
        self.layout.addWidget(self.repeatButton)
        self.layout.addWidget(self.versionLabel)

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
        self.image_processing_thread.lines_complete.connect(self.handleLinesComplete)
        self.image_processing_thread.start()

        self.header_line_window = None

        self.last_clipboard_content = ''

        # self.setStyleSheet("background-color: rgba(53,53,53,255);")

        self.show()

        closeShortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        closeShortcut.activated.connect(self.shortcutClose)

    def shortcutClose(self):
        self.close()

    def handleLinesComplete(self):

        def ndarray_to_qlabel(ndarray):
            data = ndarray.copy()
            qimage = QImage(data, data.shape[1], data.shape[0], data.strides[0], QImage.Format_Grayscale8)
            qpixmap = QPixmap(qimage)
            qlabel = QLabel()
            qlabel.setPixmap(qpixmap)
            qlabel.resize(qpixmap.width(), qpixmap.height())
            return qlabel

        self.logMessage("Displaying lines...")

        auslab_image = self.image_processing_thread.auslab_image

        self.header_line_window = QWidget()
        self.header_line_window.setWindowTitle("Header Lines")
        layout = QVBoxLayout(self.header_line_window)
        # self.header_line_window.setGeometry(500, 500, 500, 500)

        for auslab_image_line in auslab_image.header_line_images:
            layout.addWidget(ndarray_to_qlabel(auslab_image_line.line_image))
            layout.addSpacing(5)

        for auslab_image_line in auslab_image.center_line_images:
            layout.addWidget(ndarray_to_qlabel(auslab_image_line.line_image))
            layout.addSpacing(5)

        # print(self.header_line_window.layout.sizeHint())

        self.header_line_window.adjustSize()
        self.header_line_window.show()

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

    def handleProcessingStateChange(self, message_str, step, total_steps):
        COMPLETED_CHAR = '*'
        # COMPLETED_CHAR = '█'
        UNCOMPLETED_CHAR = '.'
        if message_str == 'start':
            # self.processingLogo.animationStart()
            self.statusMessageLabel.setText('AUSLAB IMAGE - PROCESSING 000% [{}]'.format(UNCOMPLETED_CHAR * 10))
        elif message_str == 'stop':
            # self.processingLogo.animationStop()
            self.statusMessageLabel.setText(self.WAITING_MESSAGE)
        elif message_str == 'update':
            percentage = int((step / total_steps) * 100)
            completed_blocks = percentage // 10
            uncompleted_blocks = 10 - completed_blocks
            completed_text = COMPLETED_CHAR * completed_blocks
            uncompleted_text = UNCOMPLETED_CHAR * uncompleted_blocks

            self.statusMessageLabel.setText('AUSLAB IMAGE - PROCESSING {:03d}% [{}{}]'.format(percentage, completed_text, uncompleted_text))

    def handleProcessThreadMessage(self, message_str):
        # self.logMessage('Message signal')
        self.trayIcon.showMessage('Assist', message_str, 3000)

    def handleLogMessage(self, message):
        self.logMessage(message)

    @pyqtSlot()
    def handleRepeatButtonClicked(self):
        self.handleClipboardMessage(self.last_clipboard_content)
        # print('Repeat button pressed.')

    @pyqtSlot()
    def handleClipboardChanged(self):
        self.logMessage('Clipboard changed')

        if self.config['main']['log_clipboard_events']:
            clipboardLogFile = QFile('clipboard-log-{}-{}.txt'.format(datetime.datetime.now().strftime('%Y-%m-%d'), datetime.datetime.now().strftime('%H%M%S%f')) )
            clipboardLogFile.open(QFile.WriteOnly | QFile.Text)
            outputStream = QTextStream(clipboardLogFile)
            outputStream << "Clipboard event with type {}".format(str(QApplication.clipboard().mimeData())) << "\n"

            for mimeFormat in QApplication.clipboard().mimeData().formats():
                outputStream << str(mimeFormat) << "\n"

            outputStream << QApplication.clipboard().text()

            clipboardLogFile.close()

        qimage = QApplication.clipboard().image()
        if qimage.isNull():
            return
        self.image_queue_lock.lock()
        self.image_queue.put(qimage)
        self.image_queue_lock.unlock()
        self.logMessage('Image waiting in queue...')

    def logMessage(self, message):
        self.log_lock.lock()
        dt = datetime.datetime.now()
        datestr = dt.strftime('%d-%m-%Y %H:%M:%S')
        # print('At End: {}'.format(self.log.textCursor().atEnd()))
        textCursor = self.log.textCursor()
        textCursor.movePosition(QTextCursor.End)
        self.log.setTextCursor(textCursor)
        # print('Move successful: {}'.format(self.log.textCursor().movePosition(QTextCursor.End)))
        self.log.insertHtml('<span style=""><span style="color: #888888;">[{0}]</span> <span class="logmessage">{1}</span></span><br />'.format(datestr, html.escape(message)))
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        self.log_lock.unlock()

    def handleClipboardMessage(self, content):
        self.last_clipboard_content = content
        cp = QApplication.clipboard()
        cp.setText(content, cp.Clipboard)

    def closeEvent(self, event):
        if self.header_line_window is not None:
            self.header_line_window.close()
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

    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))

    """
    qssFile = QFile("dark.qss")
    qssFile.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(qssFile)
    app.setStyleSheet(stream.readAll())
    """

    _id = QFontDatabase().addApplicationFont('ArameMono.ttf')

    assist = Assist(config)
    # keyboard.add_hotkey('ctrl+shift+a', bringFocus, args=(assist,))
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
