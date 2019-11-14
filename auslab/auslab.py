#!/usr/bin/env python3

import sys, os, statistics
import numpy as np
import cv2
import pickle
import PIL

class AuslabImageLine:
    def __init__(self, source_image, condensed, source_coords, config, char_num=None):
        self.line_image = source_image 
        self.condensed = condensed
        self.source_coords = source_coords
        self.config = config
        if char_num is None:
            if self.condensed:
                self.char_num = self.line_image.shape[1] // self.config['condensed_char_width']
            else:
                self.char_num = self.line_image.shape[1] // self.config['char_width']
        else:
            self.char_num = char_num
    
    def getCharImages(self):
        result = []
        char_width = self.config['condensed_char_width'] if self.condensed else self.config['char_width']
        for i in range(self.char_num):
            line_x = i * char_width
            result.append(self.line_image[:,line_x:line_x+char_width])
        return result

class AuslabImage:
    # This class is designed to handle two sizes - normal and 125% scaled (latter found commonly on laptops in the hospital)
    AUSLAB_SIZE_NORMAL = 0
    AUSLAB_SIZE_LARGE = 1

    # Minimum percentage of black pixels to be considered a potential AUSLAB image
    AUSLAB_MINIMUM_BLACK = 75

    # Size expectations (normal)
    AUSLAB_MINIMUM_WIDTH = 1008
    AUSLAB_MINIMUM_HEIGHT = 730

    # Size expectations (large 125%)
    AUSLAB_MINIMUM_WIDTH_LARGE = 1258
    AUSLAB_MINIMUM_HEIGHT_LARGE = 940

    # Callback types
    CB_HEADER_LINE = 0
    CB_CENTER_LINE = 1
    CB_HEADER_LINES_COMPLETE = 2
    CB_CENTER_LINES_COMPLETE = 3

    def __init__(self, config):
        self.current_image = None
        self.input_image = None
        self._image_grey = None
        self.header_image = None
        self.body_image = None
        self.footer_image = None
        self.condensed_font = False
        self.config = config
        self.image_path = None

        self.header_line_images = []
        self.center_line_images = []

        self.valid = False
        self.size = None

        self._callbacks = {
            self.CB_HEADER_LINE : [],
            self.CB_CENTER_LINE : [],
            self.CB_HEADER_LINES_COMPLETE : [],
            self.CB_CENTER_LINES_COMPLETE : [],
        }

    def addCallback(self, cb, cb_type):
        self._callbacks[cb_type].append(cb)

    def _invokeCallbacks(self, cb_type, data):
        for cb in self._callbacks[cb_type]:
            cb(self, data)

    def loadScreenshot(self, image):
        if not isinstance(image, np.ndarray):
            # Assume it's a Qt QImage
            # TODO: Remove conversions using Qt here - find equivalent functionality on numpy array directly
            im_width = image.width()
            im_height = image.height()
            ptr = image.bits()
            ptr.setsize(image.byteCount())
        
            self.input_image = np.array(ptr).reshape(im_height, im_width, 4)
        else:
            self.input_image = image
        
        self.valid, self.size = self._detectValid(self.input_image)

        if not self.valid:
            return

        # Select sub-configuration based on size
        # Sometimes configuration is already known and passed
        if self.size is not None and 'normal' in self.config:
            if self.size == self.AUSLAB_SIZE_NORMAL:
                self.config = self.config['normal']
            elif self.size == self.AUSLAB_SIZE_LARGE:
                self.config = self.config['large']
            else:
                print('[Critical Error] Image marked as valid but has no size.  Unable to choose configuration')
                sys.exit(1)

        if 'f1_normal_template_path' in self.config:
            self.f1_normal_template = cv2.cvtColor(cv2.imread(self.config['f1_normal_template_path']), cv2.COLOR_BGR2GRAY)
        else:
            self.f1_normal_template = cv2.cvtColor(cv2.imread(os.path.join(os.path.dirname(__file__), 'F1_normal.png')), cv2.COLOR_BGR2GRAY)

        if 'f1_condensed_template_path' in self.config:
            self.f1_condensed_template = cv2.cvtColor(cv2.imread(self.config['f1_condensed_template_path']), cv2.COLOR_BGR2GRAY)
        else:
            self.f1_condensed_template = cv2.cvtColor(cv2.imread(os.path.join(os.path.dirname(__file__), 'F1_condensed.png')), cv2.COLOR_BGR2GRAY)

        self._removeScreenshotBorder()
        self._removeColors()
        self._segmentImage()
        self._detectCondensed()

    def loadScreenshotFromPIL(self, pil_image):
        open_cv_image = np.array(pil_image) 
        # Convert RGB to BGR 
        open_cv_image = open_cv_image[:, :, ::-1].copy() 
        self.loadScreenshot(open_cv_image)

    def loadScreenshotFromPath(self, image_path):
        # print("Loading screenshot from path: {}".format(image_path))
        self.image_path = image_path
        self.loadScreenshot(cv2.imread(image_path))

    def getHeaderLines(self):
        self.header_line_images = []
        for i in range(self.config['header_line_num']):
            line_y = int(self.config['line_height'] + self.config['line_spacing']) * i
            line_coords = [0, self.header_image.shape[1]-1, line_y, line_y+int(self.config['line_height'])-1]
            image_header_line = self.header_image[line_y:line_y+int(self.config['line_height']),0:self.config['header_char_num']*self.config['char_width']]
            self.header_line_images.append(AuslabImageLine(image_header_line, False, line_coords, self.config, self.config['header_char_num']))
            self._invokeCallbacks(self.CB_HEADER_LINE, self.header_line_images[-1])
        self._invokeCallbacks(self.CB_HEADER_LINES_COMPLETE, self.header_line_images)
        return self.header_line_images

    def getCenterLines(self):
        self.center_line_images = []
        # Remember that for large (scaled) images line heights and spacing may be FLOATING POINT NUMBERS
        visual_line_height = self.config['line_height'] + self.config['line_spacing']
        center_panel_height = self.center_image.shape[0]
        num_center_lines = int((center_panel_height + 1) // (self.config['line_height'] + self.config['line_spacing']))
        if center_panel_height % visual_line_height >= self.config['line_height']:
            num_center_lines += 1
        for i in range(num_center_lines):
            line_y = round(visual_line_height * i)
            line_x_start = 0
            line_x_end = self.center_image.shape[1]
            if (not self._condensed) and self.config['name'] == 'normal':
                line_x_start = 32
                line_x_end -= 16
            elif (not self._condensed) and self.config['name'] == 'large':
                line_x_start = 40
                line_x_end -= 20
            line_coords = [line_x_start, line_x_end-1, line_y, line_y+self.config['condensed_line_height']-1]
            image_center_line = self.center_image[line_y:line_y+self.config['condensed_line_height'], line_x_start:line_x_end]
            self.center_line_images.append(AuslabImageLine(image_center_line, self._condensed, line_coords, self.config))
            self._invokeCallbacks(self.CB_CENTER_LINE, self.center_line_images[-1])
        """
        for v in result[-1]:
            print(v)
        """
        # print(result[-1].getCharImages()[0])

        # print(result[0].getCharImages()[0:10])
        # sys.exit(1)
        self._invokeCallbacks(self.CB_CENTER_LINES_COMPLETE, self.center_line_images)
        return self.center_line_images

    def _detectValid(self, image):
        im_width = image.shape[1]
        im_height = image.shape[0]

        print("{} {}".format(im_width, im_height))

        if im_width >= self.AUSLAB_MINIMUM_WIDTH_LARGE and im_width < self.AUSLAB_MINIMUM_WIDTH_LARGE + 20 and im_height >= self.AUSLAB_MINIMUM_HEIGHT_LARGE and im_height < self.AUSLAB_MINIMUM_HEIGHT_LARGE + 20:
            print('Image is likely large...')
            if self._countBlackPercentage(image) < self.AUSLAB_MINIMUM_BLACK:
                return (False, None)
            return (True, self.AUSLAB_SIZE_LARGE)

        elif im_width >= self.AUSLAB_MINIMUM_WIDTH and im_width < self.AUSLAB_MINIMUM_WIDTH + 20 and im_height >= self.AUSLAB_MINIMUM_HEIGHT and im_height < self.AUSLAB_MINIMUM_HEIGHT + 50:
            # Test for valid NORMAL image
            print("Image is likely normal...")
            if self._countBlackPercentage(image) < self.AUSLAB_MINIMUM_BLACK:
                # print('Image does not contain enough black to be an AUSLAB image!')
                return (False, None)
            return (True, self.AUSLAB_SIZE_NORMAL)

        # print('Image does not meet size criteria')
        return (False, None)

    def _countBlackPercentage(self, image):
        # TODO: Ditch OpenCV code - can all be done in numpy
        im_width = image.shape[1]
        im_height = image.shape[0]

        image_grey = cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
        image_inverted = cv2.bitwise_not(image_grey)
        _, image_thresh = cv2.threshold(image_inverted, 240, 255, 0)
        black_count = cv2.countNonZero(image_thresh)
        percentage = (black_count / (im_width * im_height)) * 100.0
        print('Black percentage: {}'.format(percentage))
        return percentage

    def _removeScreenshotBorder(self):
        # print('Removing border...')
        dimensions = self.input_image.shape
        x_min = 0
        y_min = 0
        x_max = dimensions[1] - 1
        y_max = dimensions[0] - 1

        """
        screenshot_y_border_max = self.config['screenshot_y_border_max']
        print(screenshot_y_border_max)
        print(self.config['screenshot_x_border_max'])
        """

        error_margin = self.config['border_error_margin']

        try:
            while self.input_image[self.config['screenshot_y_border_max']][x_min][0] > error_margin:
                x_min += 1
            while self.input_image[self.config['screenshot_y_border_max']][x_max][0] > error_margin:
                x_max -= 1
            while self.input_image[y_min][self.config['screenshot_x_border_max']][0] > error_margin:
                # print('Coords: [{}, {}]: {}'.format(y_min, screenshot_y_border_max, self.input_image[screenshot_y_border_max, x_min][0]))
                y_min += 1
            while self.input_image[y_max][self.config['screenshot_x_border_max']][0] > error_margin:
                y_max -= 1
        except IndexError:
            print('{0} - {1} - {2} - {3}'.format(x_min, x_max, y_min, y_max))
            raise
        
        print('Screenshot borders: {0} - {1} - {2} - {3}'.format(x_min, x_max, y_min, y_max))
        self.current_image = self.input_image[y_min:y_max+1,x_min:x_max+1]
        # sys.exit(1)

    def _log(self, log_string):
        if self.config['debug'] == True:
            print(log_string)

    def _getOutputDirectory(self):
        output_dir = os.path.join(os.path.dirname(__file__), 'interim', self.config['name'])
        return output_dir

    def _removeColors(self):
        self._image_grey = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2GRAY)
        """
        self._log('   Writing greyscale image to disk...')
        image_name = os.path.basename(os.path.splitext(self.image_path)[0])
        image_path = os.path.join(self._getOutputDirectory(), image_name + '-greyscale.png')
        cv2.imwrite(image_path, self._image_grey)
        """
        image_inverted = cv2.bitwise_not(self._image_grey)
        _, image_thresh = cv2.threshold(image_inverted, 240, 255, 0)
        self.current_image = image_thresh

    def _segmentImage(self):
        self.header_image = self.current_image[self.config['header_y_start']:self.config['header_y_end']+1,self.config['header_x_start']:self.config['header_x_end']+1]
        self.center_image = self.current_image[self.config['central_panel_y_start']:self.config['central_panel_y_end']]
        self.footer_image = self.current_image[self.config['central_panel_y_end']+1:]

        """
        image_name = os.path.basename(os.path.splitext(self.image_path)[0])
        new_path = os.path.join(self._getOutputDirectory(), image_name + '-{}') + '.png'
        self._log('   Segmented - outputing interim data to {}'.format(new_path))

        cv2.imwrite(new_path.format('header'), self.header_image)
        cv2.imwrite(new_path.format('center'), self.center_image)
        cv2.imwrite(new_path.format('footer'), self.footer_image)
        """

    def _detectCondensed(self):
        footer_image_grey = self._image_grey[self.config['central_panel_y_end']+1:]
        normal_match = np.max(cv2.matchTemplate(footer_image_grey, self.f1_normal_template, cv2.TM_CCOEFF))
        condensed_match = np.max(cv2.matchTemplate(footer_image_grey, self.f1_condensed_template, cv2.TM_CCOEFF))
        self._condensed = condensed_match >= normal_match

class AuslabTemplateRecognizer():

    def __init__(self, config):
        self.normal_templates = {}
        self.condensed_templates = {}
        self.config = config
        template_file = None
        if 'template_file_path' in self.config:
            print('AuslabTemplateRecognizer loading specified template file: {}'.format(self.config['template_file_path']))
            template_file = open(self.config['template_file_path'], 'rb')
            [n_t, c_t] = pickle.load(template_file)
            self.normal_templates = n_t
            self.condensed_templates = c_t
            template_file.close()
            """
            else:
                print('AuslabTemplateRecognizer loading pre-packaged template file...')
                template_file = open(os.path.join(os.path.dirname(__file__), 'templates.dat'), 'rb')
            """
        else:
            self.clearTemplates()

        # Stats:
        print("Number of normal templates: {}".format(len(self.normal_templates)))
        print("Number of condensed templates: {}".format(len(self.condensed_templates)))
        if len(self.normal_templates) > 0:
            normal_template_numbers = [len(v) for k, v in self.normal_templates.items()]
            condensed_template_numbers = [len(v) for k, v in self.condensed_templates.items()]
            # print(normal_template_numbers)
            # print(condensed_template_numbers)
            """
            for k, v in self.normal_templates.items():
                if len(v) > 10:
                    print(k)
                    print('   {}'.format(len(v)))
                for t in v:
                    print('   {}'.format(t.shape))
            """

            """
            for i, v in enumerate(self.condensed_templates[' ']):
                print(v)
                if i > 10:
                    break
            """
            
            print("Normal template statistics: min: {}    max: {}    median: {}".format(min(normal_template_numbers), max(normal_template_numbers), int(statistics.median(normal_template_numbers))))
            print("Condensed template statistics: min: {}    max: {}    median: {}".format(min(condensed_template_numbers), max(condensed_template_numbers), int(statistics.median(condensed_template_numbers))))

    def clearTemplates(self):
        self.normal_templates = {}
        self.condensed_templates = {}

    def trainFromImage(self, auslab_image, header_truth_lines, center_truth_lines):
        header_equalities = 0
        center_equalities = 0
        for i, header_image in enumerate(auslab_image.getHeaderLines()):
            for j, char_image in enumerate(header_image.getCharImages()):
                truth_char = header_truth_lines[i][j]
                if truth_char not in self.normal_templates:
                    self.normal_templates[truth_char] = []
                char_image = char_image / 255.0
                exists = False
                for image in self.normal_templates[truth_char]:
                    if np.array_equal(image, char_image):
                        exists = True
                        header_equalities += 1
                        break
                if not exists:
                    self.normal_templates[truth_char].append(char_image)
        for i, center_image in enumerate(auslab_image.getCenterLines()):
            for j, char_image in enumerate(center_image.getCharImages()):
                truth_char = center_truth_lines[i][j]
                templates = self.condensed_templates if center_image.condensed else self.normal_templates
                if truth_char not in templates:
                    templates[truth_char] = []
                char_image = char_image / 255.0
                exists = False
                
                """
                if truth_char == ' ' and np.sum(char_image) < (char_image.size - 10):
                    print('*** {} , {}'.format(j, i))
                    print(char_image)
                """
                
                for image in templates[truth_char]:
                    if np.array_equal(image, char_image):
                        exists = True
                        center_equalities += 1
                        break
                if not exists:
                    templates[truth_char].append(char_image)
        # print('  Header equalities: {}'.format(header_equalities))
        # print('  Center equalities: {}'.format(center_equalities))

    def saveTemplates(self, template_file_path):
        output_file = open(template_file_path, 'wb')
        pickle.dump([self.normal_templates, self.condensed_templates], output_file)
        output_file.close()


    def recognizeLine(self, auslab_line):
        line_str = ''
        for char_image in auslab_line.getCharImages():
            line_str += self.recognizeChar(char_image, auslab_line.condensed)
        return line_str


    def recognizeChar(self, char_image, condensed):
        if np.max(char_image) > 1.0:
            char_image = char_image / 255.0
        if cv2.countNonZero(char_image) == np.size(char_image):
            return ' '
        templates = self.condensed_templates if condensed else self.normal_templates

        min_diff = self.config['char_width'] * self.config['condensed_line_height']
        best_letter = 'x'
        for letter, template_list in templates.items():
            for template in template_list:
                diff = np.sum(np.absolute(char_image - template))
                if diff < min_diff:
                    best_letter = letter
                    min_diff = diff
        return best_letter


    def dumpTemplates(self, output_dir):
        for i, (letter, templates) in enumerate(self.normal_templates.items()):
            for j, template in enumerate(templates):
                output_filename = 'normal-{0}-{1}-{2}.png'.format(i,letter,j)
                x = (template * 255.0).astype(int)
                cv2.imwrite(os.path.join(output_dir, output_filename), x)
        for i, (letter, templates) in enumerate(self.condensed_templates.items()):
            for j, template in enumerate(templates):
                output_filename = 'condensed-{0}-{1}-{2}.png'.format(i,letter,j)
                x = (template * 255.0).astype(int)
                cv2.imwrite(os.path.join(output_dir, output_filename), x)


def main():
    print('This file should not be run directly.')
    sys.exit(1)

if __name__ == '__main__':
    main()