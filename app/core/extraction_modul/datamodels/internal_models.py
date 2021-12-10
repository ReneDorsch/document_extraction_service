from __future__ import annotations
import re
from collections import defaultdict
from typing import List, Tuple, Dict
import copy
import fitz


################################################################################
################################################################################
################################################################################
class DataBlock:
    '''

    Baseclass of all BlockClasses (TextBlock, ClassBlock). Each DataBlock contains the
    Position of the Block on a Site, and the Page in the Document.
    It is the Interface to the Library PyMuPdf.
    '''


    def __init__(self, dataBlockID: int, pageNum: int = 9999, dataBlock: DataBlock = None):
        posX1, posY1, posX2, posY2 = self.extractPositionOfDataBlock(dataBlock)
        self.posX1 = int(posX1)
        self.posY1 = int(posY1)
        self.posX2 = int(posX2)
        self.posY2 = int(posY2)
        self.position = (self.posX1, self.posY1, self.posX2, self.posY2)
        self.absY1: int = 0
        self.absY2: int = 0
        self.pageNum = int(pageNum)
        self.ID = dataBlockID



    def extractPositionOfDataBlock(self, dataBlock: DataBlock):
        if dataBlock is None:
            return (0, 0, 0, 0)
        return dataBlock['bbox']

################################################################################
################################################################################
################################################################################
class ImageBlock(DataBlock):
    def __init__(self,dataBlockID: int, pageNum: int, dataBlock: DataBlock):
        super().__init__(dataBlockID, pageNum, dataBlock)
        self.image: str = dataBlock
        self.hasSubtitleTextBlocks: List[TextBlock] = None
        self.hasSubtitle: str = ""

################################################################################
################################################################################
################################################################################
class TextBlock(DataBlock):
    NORMAL_WIDTH_OF_A_SPACE = 2
    NORMAL_DISTANCE_BETWEEN_TWO_LINES = 2
    FONTS = []
    SIZES = []
    def __init__(self, dataBlockID: int, pageNum: int = -9999, dataBlock = None, rawDataBlock= None):
        super().__init__(dataBlockID, pageNum, dataBlock)
        self.text: str = " "
        self.startsLower: bool = None
        self.endsWithoutPoint: bool = None
        self.isPartOfText: bool = True
        self.isPartOfTable: bool = False
        self.isPartOfImage: bool = False
        self.isPartOfMeta: bool = False
        self.isHeader: bool = False
        self.startsWith: TextBlock = None
        self.endsWith: TextBlock = None
        self.isRecurringElement: bool = False
        self.lines: List[Line] = self.extractLinesOfTextBlock(dataBlock, pageNum)
        #self.rawLines: 'dict' = self.extractLinesOfTextBlock(rawDataBlock)
        self.orientation: int = self.getOrientation()
        self.size = self.get_size()
        self.font = self.get_font()

        self.extractTextOfTextBlock()
        self.checkBeginningAndEnding()

    @classmethod
    def create_from_pages(cls, pages, width, height):
        res = []
        dataBlockID = 0
        for pageNum, page in enumerate(pages):
            blocks = TextBlock.update_data(page.getText("dict"))
            blocks_raw = TextBlock.update_data(page.getText("rawdict"))


            for num, dataBlock in enumerate(blocks["blocks"]):
                dataBlockID += 1
                # Datablock is a Text
                if dataBlock["type"] == 0:
                    textB = TextBlock(dataBlockID, pageNum, dataBlock, blocks_raw['blocks'][num])
                    res.append(textB)

        return res


    @staticmethod
    def update_data(data) -> Dict:
        ''' Controlls the textblock. '''


        blocks = data['blocks']
        new_blocks = []
        for block in blocks:
            if block['type'] == 1:
                new_blocks.extend(TextBlock._update_image_block(block))
            else:
                new_blocks.extend(TextBlock._update_text_block(block))



        return { 'width': data['width'],
                 'height': data['height'],
                 'blocks': new_blocks
                }

    @staticmethod
    def _update_text_block(text_block: Dict) -> List[Dict]:
        ''' Controlls the image_file block'''
        bboxs = []
        lines: List[Dict] = text_block['lines']
        has_more_than_one_line: bool = len(lines) > 1

        for line in lines:
            for span in line['spans']:
                if "text" in span:
                    if "Table 1." in span['text']:
                        print("ok")
        if has_more_than_one_line:
            new_lines = [lines[0]]
            for idx, line in enumerate(lines[1:]):
                prevLine = lines[idx - 1]

                prevY1 = prevLine['bbox'][1]
                prevY2 =  prevLine['bbox'][3]
                y1 = line['bbox'][1]
                y2 = line['bbox'][3]

                distance_is_longer_than_a_normal_height: bool = y1 - prevY2 > TextBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES * 1.05
                is_in_same_line: bool = y1 <= prevY1 <= y2 or y1 <= prevY2 <= y2 or prevY1 <= y1 <= prevY2 or prevY1 <= y1 <= prevY2
                if distance_is_longer_than_a_normal_height and not is_in_same_line:
                    new_block = {'type': 0,
                                 'bbox': (min([_['bbox'][0] for _ in new_lines]),
                                          min([_['bbox'][1] for _ in new_lines]),
                                          max([_['bbox'][2] for _ in new_lines]),
                                          max([_['bbox'][3] for _ in new_lines])),
                                 'lines': new_lines}
                    new_lines = [line]
                    bboxs.append(new_block)
                else:
                    new_lines.append(line)
                    continue

        else:
            return [text_block]

        if len(new_lines) > 0:
            new_block = {'type': 0,
                         'bbox': (min([_['bbox'][0] for _ in new_lines]),
                                  min([_['bbox'][1] for _ in new_lines]),
                                  max([_['bbox'][2] for _ in new_lines]),
                                  max([_['bbox'][3] for _ in new_lines])),
                         'lines': new_lines}
            bboxs.append(new_block)
        return bboxs

    @staticmethod
    def _update_image_block(image_block: Dict) -> List[Dict]:
        ''' Controlls the image_file block'''
        # Do nothing because i dont use it.
        return [image_block]


    def get_size(self) -> str:
        sizes = defaultdict(int)
        for line in self.lines:
            sizes[line.mostCommonSizeInTextBlock] += 1

        sizes = list(sizes.items())
        sizes.sort(key=lambda x: x[1], reverse=True)
        if len(sizes) == 0:
            return -1
        return sizes[0][0]

    def get_font(self) -> str:
        sizes = defaultdict(int)
        for line in self.lines:
            sizes[line.mostCommonFontInTextBlock] += 1

        sizes = list(sizes.items())
        sizes.sort(key=lambda x: x[1], reverse=True)
        if len(sizes) == 0:
            return 'Unknown'
        return sizes[0][0]

    def is_part_of(self, page, x1, y1, x2, y2) -> bool:
        if page == self.pageNum:
            if x1 <= self.posX1 <= x2 or x1 <= self.posX2 <= x2:
                if y1 <= self.posY1 <= y2 or y1 <= self.posY2 <= y2:
                    return True
        return False


    def set_absolute_positions_of_lines(self):

        for line in self.lines:
            line.absY2 = self.absY1 + (line.posY2 - self.posY1)
            line.absY1 = self.absY1 + (line.posY1 - self.posY1)


    def getOrientation(self):
        '''
        Returns the Orientation of the TextBlock
        :return: 0 for horizontalLinesAndLeftToRight
                 1 for horizontalLinesAndRightToLeft
                 2 for verticalLinesAndLeftToRight
                 3 for verticalLinesAndRightToLeft
        '''
        horizontalLinesAndLeftToRight = 0
        horizontalLinesAndRightToLeft = 0
        verticalLinesAndLeftToRight = 0
        verticalLinesAndRightToLeft = 0
        res = [horizontalLinesAndLeftToRight, horizontalLinesAndRightToLeft, verticalLinesAndLeftToRight,
               verticalLinesAndRightToLeft]
        for line in self.lines:
            if line.dir[0] >= 0:
                if line.dir[1] >= 0: res[0] += 1
                else: res[1] += 1
            else:
                if line.dir[1] >= 0: res[2] += 1
                else: res[3] += 1

        return res.index(max(res))





    @staticmethod
    def setSpaceSize(space: float):
        TextBlock.NORMAL_WIDTH_OF_A_SPACE = space

    @staticmethod
    def setSizes(sizes: List[Tuple[int, int]]):
        TextBlock.SIZES = sizes

    @staticmethod
    def setFonts(fonts: List[Tuple[int, int]]):
        TextBlock.FONTS = fonts

    @staticmethod
    def setDistanceBetweenTwoLines(distance: float):
        TextBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES = distance

    @staticmethod
    def _getHeightsBetweenLines2(pages) -> List:
        heights = defaultdict(int)
        lines = []

        # Get all lines
        for pageNum, page in enumerate(pages):
            dataBlocks = [_dataBlocks for key, _dataBlocks in page.getText("rawdict").items() if key == "blocks"][0]
            for textBlock in dataBlocks:
                if textBlock['type'] == 0: # If it is of type text
                    for line in textBlock['lines']:
                        line.update({'page': pageNum})
                    lines.extend(textBlock['lines'])


        # count the distance between each line of the textBlocks
        for idx_, line in enumerate(lines[1:]):
            prevLine = lines[idx_ - 1]
            prevPage = prevLine['page']
            page = line['page']
            prevY1 = prevLine['bbox'][1]
            prevY2 = prevLine['bbox'][3]
            y1 = line['bbox'][1]
            y2 = line['bbox'][3]
            delta = int(y1 - prevY2)
            is_in_same_line: bool = y1 <= prevY1 <= y2 or y1 <= prevY2 <= y2 or prevY1 <= y1 <= prevY2 or prevY1 <= y1 <= prevY2
            if 0 <= delta and prevPage == page and not is_in_same_line:
                heights[delta] += 1

        heights: List = list(heights.items())
        heights.sort(key=lambda x: x[1], reverse=True)
        return heights

    def _getHeightsBetweenLines(self, pages) -> List:


        heightBetweenLines = {}
        for page in pages:
            dataBlocks = [_dataBlocks for key, _dataBlocks in page.getText("rawdict").items() if key == "blocks"][0]
            textBlocks = [textBlock for textBlock in dataBlocks if textBlock['type'] == 0]
            for textBlock in textBlocks:
                prevPosY2 = -9999
                for line in textBlock["lines"]:
                    if prevPosY2 == -9999:
                        prevPosY2 = line['bbox'][3]
                    else:
                        # Calculation of the Distance between two lines
                        heightBetweenTwoLines = int(prevPosY2 - line['bbox'][1])
                        prevPosY2 = line['bbox'][3]
                        if heightBetweenTwoLines >= 0:
                            if str(heightBetweenTwoLines) not in heightBetweenLines:
                                heightBetweenLines[str(heightBetweenTwoLines)] = 1
                            else:
                                heightBetweenLines[str(heightBetweenTwoLines)] += 1

        heightBetweenLines = [(int(distance), count) for distance, count in heightBetweenLines.items()]
        heightBetweenLines.sort(key=lambda x: x[1], reverse=True)
        return heightBetweenLines



    @staticmethod
    def _get_space_between_chars(pages: fitz.Page) -> List:
        distancesBetweenTwoChars = {}
        for page in pages:
            dataBlocks = [_dataBlocks for key, _dataBlocks in page.getText("rawdict").items() if key == "blocks"][0]
            textBlocks = [textBlock for textBlock in dataBlocks if textBlock['type'] == 0]
            for textBlock in textBlocks:
                for line in textBlock["lines"]:
                    for span in line["spans"]:
                        prevCharPosX2 = -9999
                        for char in span["chars"]:
                            if prevCharPosX2 == -9999:
                                prevCharPosX2 = char['bbox'][2]
                            else:
                                # Calculation of the Space between two Chars
                                distanceBetweenTwoChars = int(prevCharPosX2 - char['bbox'][0])
                                prevCharPosX2 = char['bbox'][2]
                                if distanceBetweenTwoChars >= 0:
                                    if str(distanceBetweenTwoChars) not in distancesBetweenTwoChars:
                                        distancesBetweenTwoChars[str(distanceBetweenTwoChars)] = 1
                                    else:
                                        distancesBetweenTwoChars[str(distanceBetweenTwoChars)] += 1
        distancesBetweenTwoChars = [(int(distance), count) for distance, count in distancesBetweenTwoChars.items()]
        distancesBetweenTwoChars.sort(key=lambda x: x[1], reverse=True)
        return distancesBetweenTwoChars

    @staticmethod
    def _get_space_between_chars(pages, width: int) -> List:
        distancesBetweenTwoChars = defaultdict(int)

        chars = []

        # Get all chars
        for page in pages:
            dataBlocks = [_dataBlocks for key, _dataBlocks in page.getText("rawdict").items() if key == "blocks"][0]
            textBlocks = [textBlock for textBlock in dataBlocks if textBlock['type'] == 0]
            for textBlock in textBlocks:
                for line in textBlock["lines"]:
                    for span in line["spans"]:
                        chars.extend(span["chars"])

        # Calculate the difference between two chars
        for idx_, char in enumerate(chars[1:]):
            prev_char_x2 = chars[idx_ - 1]['bbox'][2]
            char_x1 = char['bbox'][0]
            # Calculation of the Space between two Chars
            delta = int(char_x1 - prev_char_x2)

            if 0 <= delta <= width:
                distancesBetweenTwoChars[delta] += 1

        distancesBetweenTwoChars = list(distancesBetweenTwoChars.items())
        distancesBetweenTwoChars.sort(key=lambda x: x[1], reverse=True)
        return distancesBetweenTwoChars

    @staticmethod
    def _get_sizes(pages) -> List:

        typesOfSizes = defaultdict(int)
        for page in pages:
            dataBlocks = [_dataBlocks for key, _dataBlocks in page.getText("rawdict").items() if key == "blocks"][0]
            textBlocks = [textBlock for textBlock in dataBlocks if textBlock['type'] == 0]
            for textBlock in textBlocks:
                for line in textBlock["lines"]:
                    size = int(line["spans"][0]['size'])

                    typesOfSizes[size] += 1

        sizes = list(typesOfSizes.items())

        sizes.sort(key=lambda x: x[1], reverse=True)
        return sizes

    @staticmethod
    def _get_fonts(pages) -> List:
        typesOfFonts = defaultdict(int)
        for page in pages:
            dataBlocks = [_dataBlocks for key, _dataBlocks in page.getText("rawdict").items() if key == "blocks"][0]
            textBlocks = [textBlock for textBlock in dataBlocks if textBlock['type'] == 0]
            for textBlock in textBlocks:
                for line in textBlock["lines"]:
                    font = line["spans"][0]['font']
                    typesOfFonts[font] += 1



        fonts = list(typesOfFonts.items())
        fonts.sort(key=lambda x: x[1], reverse=True)

        return fonts


    @staticmethod
    def initializeParameters(pages, width):

        # Calculates the initliation parameters
        distancesBetweenTwoChars = TextBlock._get_space_between_chars(pages, width)
        heightBetweenLines = TextBlock._getHeightsBetweenLines2(pages)
        sizes = TextBlock._get_sizes(pages)
        fonts = TextBlock._get_fonts(pages)


        TextBlock.NORMAL_WIDTH_OF_A_SPACE = TextBlock.getHigherDistance(distancesBetweenTwoChars)
        TextBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES = TextBlock.getHigherDistance(heightBetweenLines)
        TextBlock.FONTS = fonts
        TextBlock.SIZES = sizes

    @staticmethod
    def getHigherDistance(values):
        # Get the next bigger value to 1
        if len(values) > 1:
            # Get the next higher distance to 0
            _values = [distance for distance, __ in values if distance > 1]
            return _values[0]
        else:
            return 2






    def isParagraph(self) -> bool:
        '''
        Checks if a TextBlock is a Paragraph
        :return: true if Paragraph, false if not
        '''

        text = self.text
        text = text.lstrip()
        text = re.sub("\s+$", "", text)
        if len(text) > 1:
            reg = re.findall(r'[A-Z]', text[0])
            if reg != []: self.startsLower = False
            else: self.startsLower = True
            if text[-1] == "." or text[-1] == ";": self.endsWithoutPoint = False
            else: self.endsWithoutPoint = True
            if self.startsLower is False and self.endsWithoutPoint is False:
                return True
        return False

    def extractTextOfTextBlock(self) -> str:
        '''
        Extracts the lines of a TextBlock and merges them as one TextBlock.
        In addition it also handles the Problems with "-" between two lines
        :param textBlock:
        :return: text of the TextBlock as string
        '''
        textLines = []
        prevSpanText = ""

        for num, line in enumerate(self.lines):
            textLine = []

            spanPosY1 = line.posY1
            spanPosY2 = line.posY2

            # Checks the distance between two spans
            if num > 0:
                if spanPosY1 - prevSpanPosY2 > TextBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES:
                    textLine.append(" ")
            # Checks for "-" before new Line
            textLines = self.identifyNewLine(line, prevSpanText, textLine, textLines)
            prevSpanPosY2 = spanPosY2
            prevSpanText = line.textInLine

            textLine.append(" ")
            textLines.extend(textLine)

        text = "".join(textLines)
        # Deletes additional Spaces between two words
        self.text = re.sub(" +", " ", text)
        return text

    def identifyNewLine(self, line, prevSpanText, textLine, textLines):

        def replaceLastOccurence(string: str, find, replace):
            reversed = string[::-1]
            replaced = reversed.replace(find[::-1], replace[::-1], 1)
            return replaced[::-1]

        prevLineWithlineScore = prevSpanText.replace(" ", "").endswith("-")
        if len(line.textInLine.replace(" ", "")) > 1:
            lineStartsLower = line.textInLine.replace(" ", "")[0].islower()
        else:
            lineStartsLower = False
        textLine.append(line.textInLine)
        # Check if the span ends with an -
        # E.g. sys-
        #      tem
        if prevLineWithlineScore and lineStartsLower:
            if len(textLine) > 1:
                textLine[len(textLine) - 1] = replaceLastOccurence(textLine[len(textLine) - 1], "-", "")
            else:

                textLines[len(textLines) - 2] = replaceLastOccurence(textLines[len(textLines) - 2], "-", "")
                textLines = textLines[:-1]
        return textLines





    def checkBeginningAndEnding(self) -> bool:
        '''
        Checks if a TextBlock is a Paragraph
        :return: true if Paragraph, false if not
        '''

        text = self.text
        text = text.lstrip()
        text = re.sub("\s+$", "", text)
        if len(text) > 1:
            reg = re.findall(r'[A-Z]', text[0])
            if reg != []:
                self.startsLower = False
            else:
                self.startsLower = True
            if text[-1] == "." or text[-1] == ";":
                self.endsWithoutPoint = False
            else:
                self.endsWithoutPoint = True
            if self.startsLower is False and self.endsWithoutPoint is False:
                return True
        return False

    def extractLinesOfTextBlock(self, textBlock, pageNum) -> List['Line']:

        lines = []
        if textBlock is None:
            return lines
        textBlockLines = copy.copy(textBlock['lines'])
        while(True):
            if len(textBlockLines) == 0: break
            textBlockLine = textBlockLines.pop(0)
            line = Line(textBlockLine, textBlockLines, self, pageNum)
            for element in line.getLinesToDelete():
                if element in textBlockLines:
                    textBlockLines.remove(element)
            lines.append(line)


        return lines


class Line:

    def __init__(self, line, lines, textBlock, pageNum):
        posX1, posY1, posX2, posY2 = self.extractPositionOfLine(line)
        self.posX1 = int(posX1)
        self.posY1 = int(posY1)
        self.posX2 = int(posX2)
        self.posY2 = int(posY2)
        self.absY2 = 0
        self.absY1 = 0
        self.pageNum = pageNum
        self.dir: Tuple = line['dir']
        self.linesInDict = []
        self.width = self.posY2 - self.posY1

        self.position = (self.posX1, self.posY1, self.posX2, self.posY2)
        self.textInLine = self.extractTextInLine(line, lines, textBlock)
        self.mostCommonSizeInTextBlock: int = 0
        self.mostCommonFontInTextBlock: str = ''
        self.fontsInLine = self.extractFontsInLine()
        self.fontSizesInLine = self.extractFontSizesInLine()


        self.updateCoordinates()


    def updateCoordinates(self):
        posX1, posY1, posX2, posY2 = 9999, 9999, -9999, -9999
        for line in self.linesInDict:
            posLineX1, posLineY1, posLineX2, posLineY2 = self.extractPositionOfLine(line)
            if posLineX1 < posX1: posX1 = posLineX1
            if posLineY1 < posY1: posY1 = posLineY1
            if posLineX2 > posX2: posX2 = posLineX2
            if posLineY2 > posY2: posY2 = posLineY2
        self.posX1 = int(posX1)
        self.posY1 = int(posY1)
        self.posX2 = int(posX2)
        self.posY2 = int(posY2)
        self.position = posX1, posY1, posX2, posY2



    def extractFontsInLine(self):
        res = defaultdict(int)
        for line in self.linesInDict:
            for span in line['spans']:
                res[span['font']] += 1

        res = list(res.items())
        res.sort(key=lambda x: x[1], reverse=True)
        return [_[0] for _ in res]

    def extractFontSizesInLine(self):
        res = defaultdict(int)
        for line in self.linesInDict:
            # Includes only for one span in each line the size
            size = int(line['spans'][0]['size'])
            res[size] += 1
        sizesInTextBlock = [(fontSize, counts) for fontSize, counts in res.items()]
        sizesInTextBlock.sort(key=lambda x: x[1], reverse=True)
        try:
            self.mostCommonSizeInTextBlock = int(sizesInTextBlock[0][0])
        except IndexError:
            self.mostCommonSizeInTextBlock = -9999
        return [_ for _ in res.keys()]

    def getLinesToDelete(self):
        return self.linesInDict

    def extractPositionOfLine(self, line):
        posX1, posY1, posX2, posY2 = 9999, 9999, -9999, -9999
        for span in line['spans']:
            if span['bbox'][0] < posX1: posX1 = span['bbox'][0]
            if span['bbox'][1] < posY1: posY1 = span['bbox'][1]
            if span['bbox'][2] > posX2: posX2 = span['bbox'][2]
            if span['bbox'][3] > posY2: posY2 = span['bbox'][3]
        return posX1, posY1, posX2, posY2

    def extractTextInLine(self, line, lines, textBlock: TextBlock):

        text = "".join([_['text'] for _ in line['spans']])
        HEIGHT_OF_LINE  = textBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES
        WIDTH_OF_SPACE = textBlock.NORMAL_WIDTH_OF_A_SPACE
        linesToDelete = []
        linesToDelete.append(line)
        prevX2 = self.posX2
        for lineInTextBlock in lines:
            if lineInTextBlock is not line:
                sameRow: bool = self.posY1 - 0.5 * HEIGHT_OF_LINE <= int(lineInTextBlock['bbox'][1]) <= self.posY1 + 0.5 * \
                                   HEIGHT_OF_LINE and self.posY2 - 0.5 * HEIGHT_OF_LINE <= int(lineInTextBlock['bbox'][3]) <= \
                                   self.posY2 + 0.5 * HEIGHT_OF_LINE

                if sameRow:
                    for span in lineInTextBlock['spans']:
                        if -0.5 * WIDTH_OF_SPACE <= span['bbox'][0] - prevX2 <= 0.5 * WIDTH_OF_SPACE:
                            text += span['text']
                        else:
                            text += " " + span['text']
                        prevX2 = span['bbox'][2]
                    linesToDelete.append(lineInTextBlock)
            prevX2 = lineInTextBlock['bbox'][2]

        self.linesInDict = linesToDelete
        return text


    def getSpans(self, orientation):
        res = []
        for line in self.linesInDict:
            res.extend(line['spans'])
        if orientation == 1:
            res.sort(key=lambda x: x['bbox'][1], reverse=True)
        elif orientation == 0:
            res.sort(key=lambda x: x['bbox'][0])
        return res