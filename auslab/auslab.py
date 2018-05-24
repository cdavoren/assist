#!/usr/bin/env python3

import sys, os
import numpy as np
import cv2
import pickle
import PIL

# AUSLAB_SCREENSHOT_Y_BORDER_MAX = 60
# AUSLAB_SCREENSHOT_X_BORDER_MAX = 15

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

# AUSLAB_F1_NORMAL = cv2.cvtColor(cv2.imread('auslab/F1_normal.png'), cv2.COLOR_BGR2GRAY)
# AUSLAB_F1_CONDENSED = cv2.cvtColor(cv2.imread('auslab/F1_condensed.png'), cv2.COLOR_BGR2GRAY)

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
        # print(self.config)
        result = []
        char_width = self.config['condensed_char_width'] if self.condensed else self.config['char_width']
        for i in range(self.char_num):
            line_x = i * char_width
            result.append(self.line_image[:,line_x:line_x+char_width])
        return result

class AuslabImage:
    def __init__(self, config):
        self.current_image = None
        self.input_image = None
        self._image_grey = None
        self.header_image = None
        self.body_image = None
        self.footer_image = None
        self.condensed_font = False
        self.config = config

        self.f1_normal_template = cv2.cvtColor(cv2.imread(self.config['f1_normal_template_path']), cv2.COLOR_BGR2GRAY)
        self.f1_condensed_template = cv2.cvtColor(cv2.imread(self.config['f1_condensed_template_path']), cv2.COLOR_BGR2GRAY)

    def loadScreenshot(self, image):
        self.input_image = image        
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
        self.loadScreenshot(cv2.imread(image_path))

    def getHeaderLines(self):
        # line_height = AUSLAB_LINE_HEIGHT + AUSLAB_LINE_SPACING
        result = []
        for i in range(self.config['header_line_num']):
            line_y = (self.config['line_height'] + self.config['line_spacing']) * i
            line_coords = [0, self.header_image.shape[1]-1, line_y, line_y+self.config['line_height']-1]
            image_header_line = self.header_image[line_y:line_y+self.config['line_height'],0:self.config['header_char_num']*self.config['char_width']]
            # print(AUSLAB_HEADER_CHAR_NUM*AUSLAB_CHAR_WIDTH)
            result.append(AuslabImageLine(image_header_line, False, line_coords, self.config, self.config['header_char_num']))
        return result

    def getCenterLines(self):
        result = []
        visual_line_height = self.config['line_height'] + self.config['line_spacing']
        center_panel_height = self.center_image.shape[0]
        num_center_lines = (center_panel_height + 1) // (self.config['line_height'] + self.config['line_spacing'])
        if center_panel_height % visual_line_height >= self.config['line_height']:
            num_center_lines += 1
        for i in range(num_center_lines):
            line_y = visual_line_height * i
            line_x_start = 0
            line_x_end = self.center_image.shape[1]
            if not self._condensed:
                line_x_start = 32
                line_x_end -= 16
            line_coords = [line_x_start, line_x_end-1, line_y, line_y+self.config['condensed_line_height']-1]
            image_center_line = self.center_image[line_y:line_y+self.config['condensed_line_height'], line_x_start:line_x_end]
            # cv2.imwrite('lines/'+filename_base+'.center{0}.cropped.'.format(i+1)+FILENAME_EXTENSION, im_center_line)
            result.append(AuslabImageLine(image_center_line, self._condensed, line_coords, self.config))

            # im_center_line_dotted,spans = add_dots_to_line(im_center_line, condensed)
            # cv2.imwrite('lines-dotted/'+filename_base+'.center{0}.cropped.'.format(i+1)+FILENAME_EXTENSION, im_center_line_dotted)

        return result

    def _removeScreenshotBorder(self):
        dimensions = self.input_image.shape
        x_min = 0
        y_min = 0
        x_max = dimensions[1] - 1
        y_max = dimensions[0] - 1

        print('{0} x {1}'.format(self.config['screenshot_x_border_max'],self.config['screenshot_y_border_max']))

        try:
            while self.input_image[self.config['screenshot_y_border_max']][x_min][0] != 0:
                x_min += 1
            while self.input_image[self.config['screenshot_y_border_max']][x_max][0] != 0:
                x_max -= 1
            while self.input_image[y_min][self.config['screenshot_x_border_max']][0] != 0:
                y_min += 1
            while self.input_image[y_max][self.config['screenshot_x_border_max']][0] != 0:
                y_max -= 1
        except IndexError:
            print('{0} - {1} - {2} - {3}'.format(x_min, x_max, y_min, y_max))
            raise
        
        self.current_image = self.input_image[y_min:y_max+1,x_min:x_max+1]

    def _removeColors(self):
        self._image_grey = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2GRAY)
        image_inverted = cv2.bitwise_not(self._image_grey)
        _, image_thresh = cv2.threshold(image_inverted, 240, 255, 0)
        self.current_image = image_thresh

    def _segmentImage(self):
        self.header_image = self.current_image[self.config['header_y_start']:self.config['header_y_end']+1,self.config['header_x_start']:self.config['header_x_end']+1]
        self.center_image = self.current_image[self.config['central_panel_y_start']:self.config['central_panel_y_end']]
        self.footer_image = self.current_image[self.config['central_panel_y_end']+1:]

    def _detectCondensed(self):
        footer_image_grey = self._image_grey[self.config['central_panel_y_end']+1:]
        normal_match = np.max(cv2.matchTemplate(footer_image_grey, self.f1_normal_template, cv2.TM_CCOEFF))
        condensed_match = np.max(cv2.matchTemplate(footer_image_grey, self.f1_condensed_template, cv2.TM_CCOEFF))
        # print('{0}: \nNormal: {1}\nCondensed: {2}'.format(filename, numpy.max(result), numpy.max(result2)))
        self._condensed = condensed_match >= normal_match

class AuslabTemplateRecognizer():

    def __init__(self, config):
        self.normal_templates = {}
        self.condensed_templates = {}
        self.config = config
        if 'template_file_path' in self.config:
            template_file = open(self.config['template_file_path'], 'rb')
            [n_t, c_t] = pickle.load(template_file)
            template_file.close()
            self.normal_templates = n_t
            self.condensed_templates = c_t
        

    def trainFromImage(self, auslab_image, header_truth_lines, center_truth_lines):
        for i, header_image in enumerate(auslab_image.getHeaderLines()):
            # print('  header-{0}'.format(i+1))
            for j, char_image in enumerate(header_image.getCharImages()):
                truth_char = header_truth_lines[i][j]
                if truth_char not in self.normal_templates:
                    self.normal_templates[truth_char] = []
                char_image = char_image / 255.0
                exists = False
                for image in self.normal_templates[truth_char]:
                    if np.array_equal(image, char_image):
                        exists = True
                        break
                if not exists:
                    # print('    Learning new {0}'.format(truth_char))
                    self.normal_templates[truth_char].append(char_image)
        for i, center_image in enumerate(auslab_image.getCenterLines()):
            # print('  center-{0}'.format(i+1))
            for j, char_image in enumerate(center_image.getCharImages()):
                truth_char = center_truth_lines[i][j]
                templates = self.condensed_templates if center_image.condensed else self.normal_templates
                if truth_char not in templates:
                    templates[truth_char] = []
                char_image = char_image / 255.0
                exists = False
                for image in templates[truth_char]:
                    if np.array_equal(image, char_image):
                        exists = True
                        break
                if not exists:
                    # print('    Learning new {0} {1}'.format('condensed' if center_image.condensed else 'normal', truth_char))
                    templates[truth_char].append(char_image)

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
        # if np.sum(char_image) == np.size(char_image):
            # return ' '
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