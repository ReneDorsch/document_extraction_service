from __future__ import annotations

import copy
from collections import defaultdict
from typing import List
from fuzzywuzzy import fuzz
from app.core.extraction_modul.datamodels.internal_models import TextBlock
from segtok.segmenter import split_single

from ...detection_models.text_detection import is_grammatically_sentence
import app.core.schemas.datamodels as io
from ..apis.util_functions import check_for_metadata
import re


class Text:
    IDCounter = 0

    def __init__(self, textBlocks, width_of_space: int, distance_between_lines: int, sizes: list, fonts: list):
        self.width_of_space = width_of_space
        self.distance_between_lines = distance_between_lines
        self.sizes = sizes
        self.fonts = fonts
        self.textBlocks: List[TextBlock] = textBlocks
        self.fullText: str = ""
        self.abstract: Chapter = None
        self.partOfTextTextBlocks = []
        self.id: int = Text.IDCounter
        Text.IDCounter += 1

    def to_io(self, metadata) -> io.Text:
        ''' Creates a Row for the responds model '''
        return io.Text(**{
            "abstract": metadata.abstract.to_io(),
            "chapters": [_.to_io() for _ in self.chapters],
            "title": metadata.title,
            "authors": [_.to_io() for _ in metadata.authors]
        })

    def save_as_dict(self):
        res = {#"id": self.id,
               "chapters": [_.save_as_dict() for _ in self.chapters]}
        return res

    def getHeadlines(self):
        pass

    def _get_textBlocks_of_tables(self, tables) -> List[TextBlock]:
        ''' Returns the textBlocks of the tables as a list. '''
        res = []
        for table in tables:
            res.extend(table.textBlocksOfTable)
        return res

    def _get_textBlocks_of_images(self, images) -> List[TextBlock]:
        ''' Returns the textBlocks of the Images as a list. '''
        res = []
        for image in images:
            res.extend(image.textBlocksOfImage)
        return res

    def _is_inside_image(self, tBlock, images) -> bool:
        textBlocks_of_images: List[TextBlock] = self._get_textBlocks_of_images(images)
        is_textBlock_of_image: bool = tBlock in textBlocks_of_images
        is_in_image_area: bool = any(image.is_inside(tBlock) for image in images)
        return is_textBlock_of_image or is_in_image_area


    def _is_inside_table(self, tBlock, tables) -> bool:
        textBlocks_of_tables: List[TextBlock] = self._get_textBlocks_of_tables(tables)
        is_textBlock_of_table: bool = tBlock in textBlocks_of_tables
        is_in_table_area: bool = any(table.is_inside(tBlock) for table in tables)
        return is_textBlock_of_table or is_in_table_area

    def _is_inside_text(self, tBlock) -> bool:
        for line in tBlock.lines:
            for chapter in self._chapters:
                if line in chapter.textLines:
                    return True

        return False
    def _is_between_two_chapters(self, tBlock):
        for _idx, chapter in enumerate(self._chapters[1:]):
            prevChapter = self._chapters[_idx - 1]
            if prevChapter.textLines[-1].absY2 <= tBlock.absY1 <= chapter.textLines[0].absY1:
                return True
        return False


    def set_headers(self):
        lineheight = TextBlock.SIZES[0][0] # the most common height of a line
        headers = copy.copy(self.headers)

        # Look for the header that is next to a chapter
        while(len(headers) > 0):

            header = headers.pop(0)
            bestFit = None
            bestDelta = 99999
            for chapter in self._chapters:
                delta = (chapter.textLines[0].absY1 - header.absY2)
                is_possible_header: bool = abs(delta) <= 5 * lineheight
                is_best_header: bool = delta < bestDelta
                has_header: bool = bestFit.has_header() if bestFit is not None else False
                if is_best_header and is_possible_header and not has_header:
                    bestFit = chapter
                    bestDelta = delta

            if bestFit is not None:
                bestFit.header = Header(header)

        # Add for every chapter without an header a empty header
        for chapter in self._chapters:
            has_header: bool = bestFit.has_header()
            if not has_header:
                chapter.header = Header()






    def identify_text(self):
        ''' Identifies the text by executing a list of rules. '''

        # Sort the text
        tBlocks = self.orderText()
        self.textBlocks = tBlocks

        # Delete information
        self.delete_duplicates()
      #  self.delete_headers()

        # Formatbased rules
        # Checking the fontsize
        tBlocks = self.identifyTextByCheckingFontSize(tBlocks)

        # Checking the width and the position of textblocks
        tBlocks = self.identifyTextOutOfOrder(tBlocks)
        tBlocks = self.checkWidthOfTextBox(tBlocks)

        # Deletes possible metadata
        tBlocks = check_for_metadata(tBlocks)

        # Updates the textBlock
        self.textBlocks = tBlocks

        self.partOfTextTextBlocks = [_ for _ in tBlocks if _.isPartOfText]

    def identify_text_area(self, width):
        ''' Identifies the text by executing a list of rules. '''

        # Sort the text
        tBlocks = self.orderText()

        # Delete information
        self.delete_duplicates()
        self.textBlocks = tBlocks

        partOfTextTextBlocks = [_ for _ in self.textBlocks if _.isPartOfText]
        columns = 5
        minX, maxX = self.getMinAndMaxWidth()
        colLength = (maxX-minX)/columns
        most_common_text_positons = self.identifyTextOutOfOrder(tBlocks, minX, maxX, colLength, columns)


        differentWidths = self._get_widths(tBlocks, width)
        normalWidth = self.getNormalWidth(differentWidths)



        #  self.delete_headers()
        most_common_font_sizes = self.getMostCommonTextSizes()
        most_common_font = self.get_most_common_fonts()
        for _idx, tBlock in enumerate(partOfTextTextBlocks):
            # Formatbased rules
            # Checking the fontsize
            has_most_common_size: bool = tBlock.size in most_common_font_sizes
            has_most_common_font: bool = tBlock.font in most_common_font

            is_in_order: bool = most_common_text_positons[int((tBlock.posX1 - minX)/colLength)]
            has_correct_width: bool = 0.95 <= int(tBlock.posX2 - tBlock.posX1)/int(normalWidth) <= 1.05
            is_metadata: bool = self.isMetaData(tBlock.text)



            case_1: bool = (has_most_common_font or has_most_common_size) and has_correct_width and not is_metadata
            case_2: bool = is_in_order and has_correct_width and not is_metadata
            case_4: bool = (has_most_common_font or has_most_common_size) and is_in_order and not is_metadata
            case_3: bool = case_1 and case_2

            tBlock.isPartOfText_1 = case_1
            tBlock.isPartOfText_2 = case_2
            tBlock.isPartOfText = case_4


        self.partOfTextTextBlocks = [_ for _ in tBlocks if _.isPartOfText]

    def get_most_common_fonts(self):
        res = []
        prevOccurences = self.fonts[0][1]
        for font, occurences in self.fonts:
            if occurences / prevOccurences < 0.6:
                break
            else:
                res.append(font)
                prevOccurences = occurences
        return res

    def setAbstract(self, abstractTextBlocks):
        lines = []
        for textBlock in abstractTextBlocks:
            lines.extend(textBlock.lines)
        abstract = Chapter(lines, self)
        self._abstract = abstract

    def remove_empty_chapters(self):
        chapters_to_remove = []
        for chapter in self._chapters:
            if not is_grammatically_sentence(chapter.textInChapter):
                chapters_to_remove.append(chapter)
        for chapter in chapters_to_remove:
            self._chapters.remove(chapter)




    def is_part_of_chapter(self, line, linePosY1, previousFontSizes, previousFonts, previousLinePosY2, textBlock, previousLine) -> bool:
        normalDistanceBetweenLines: bool = abs(linePosY1 - previousLinePosY2) <= textBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES * 1.25
        startsNotWithNumber: bool = re.search("^ *\d", line.textInLine) is None
        sameFont: bool = any([True for font in line.fontsInLine if font in previousFonts])
        sameFontSize: bool = any([True for fontSize in line.fontSizesInLine if fontSize in previousFontSizes])
        is_small: bool = len(line.textInLine.split(" ")) < 8
        header_names = ["introduction", "conclusion", "references", "results", "discussion", "experiment", "setup",
         "conflicts of interest", "funding"]
        contains_common_header_name: bool = any([word.lower() in header_names for word in line.textInLine.split(" ")])

        if previousLine is not None:
            onSamePage: bool = line.pageNum == previousLine.pageNum
            fullLine: bool = 0.9 <= ((line.posX2 - line.posX1) / (previousLine.posX2 - previousLine.posX1)) <= 1.10
            startsLower: bool = re.search("^[a-z]", line.textInLine.lstrip()) is not None
            prevEndsWithoutPoint: bool = re.search("\.$", previousLine.textInLine.rstrip()) is None

            is_header: bool = ((not(startsNotWithNumber) and not prevEndsWithoutPoint) or contains_common_header_name) and is_small
            case_1: bool = (normalDistanceBetweenLines and (sameFont or sameFontSize))
            case_2: bool = (startsLower and prevEndsWithoutPoint and (sameFont or sameFontSize))
            case_3: bool = fullLine and (sameFont or sameFontSize)
            case: bool = ((normalDistanceBetweenLines and onSamePage) or (startsLower and prevEndsWithoutPoint)) and(sameFont or sameFontSize) and not is_header
     #       if not(case_1 or case_2):
     #           print("ok")
            return case #or case_3

        return normalDistanceBetweenLines and (sameFont or sameFontSize)


    def checkWidthOfTextBox(self, textBlocks):

        zwerg = []
        textBlocksInText = [_ for _ in textBlocks if _.isPartOfText]
        differentWidths = self._get_widths(textBlocksInText)
        normalWidth = self.getNormalWidth(differentWidths)

        for width, tBlocks in differentWidths:
            x = int(width)/int(normalWidth)
            if x < 0.95 or x > 1.05:
                for textBlock in tBlocks:
                    if not self.isPartOfPreviousSentence(textBlock, textBlocksInText):
                        zwerg.append(textBlock.text)
                        textBlock.isPartOfText = False
                        # Update textBlocks in text
                        textBlocksInText = [_ for _ in textBlocks if _.isPartOfText]

        return textBlocks

    def _get_widths(self, textBlocksInText: List[TextBlock], max_width):
        differentWidths = defaultdict(int)
        for textBlock in textBlocksInText:
            width: int = textBlock.posX2 - textBlock.posX1
            # Assume that the normal width is not smaller as a quarter of the page
            if width > (max_width / 4):
                differentWidths[width] += 1

        differentWidths1 = [(x, y) for x, y in differentWidths.items()]
        differentWidths1.sort(key=lambda x: x[1], reverse=True)
        return differentWidths1

    def isPartOfPreviousSentence(self, textBlock, relevantTextBlocks):
        HEIGHT_BETWEEN_LINES = textBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES
        WIDTH_BETWEEN_WORDS = textBlock.NORMAL_WIDTH_OF_A_SPACE
        prevTextBlock = relevantTextBlocks[relevantTextBlocks.index(textBlock) - 1]

        endsWithoutPoint: bool = not prevTextBlock.text.rstrip().endswith(".")
        isInSameLine: bool = 1.25 * WIDTH_BETWEEN_WORDS <= textBlock.posX1 - prevTextBlock.posX2 <= 1.25 * \
                             WIDTH_BETWEEN_WORDS
        isInNextLine: bool = 0 <= textBlock.posY1 - prevTextBlock.posY2 <= 1.25 * HEIGHT_BETWEEN_LINES

        if (endsWithoutPoint and isInSameLine) or (endsWithoutPoint and isInNextLine):
            return True
        return False


    def getNormalWidth(self, widths):
        # Optimistic
        # Identify the most relevant Tuples
        prevLength = 1
        zwerg = []
        for width, frequency in widths:
            if frequency/prevLength > 0.75:
                zwerg.append(int(width))
                prevLength = frequency
            else:
                break
        return max(zwerg)



    def checkGrammaticalySentences(self, textBlocks):
        for textBlock in textBlocks:
            correctSentences: List[bool] = []
            sentences = split_single(textBlock.text)
            if len(sentences) == 0: textBlock.isPartOfText = False
            for sentence in sentences:
                correctSentences.append(is_grammatically_sentence(sentence))

            if not any(correctSentences): textBlock.isPartOfText = False

        return textBlocks



    def get_delete_duplicates(self, repeating: int = 2, threshold: int=50) -> List[TextBlock]:
        duplicates: List[TextBlock] = []
        duplicates = self.get_geometrical_duplicates(self.textBlocks, duplicates, repeating)# deleteGeometricalRepeating(repeating)
        duplicates = self.get_textual_duplicates(self.textBlocks, duplicates, threshold) #self.deleteTextualRepeating(threshold)
        return duplicates


    def get_textual_duplicates(self, textBlocks, duplicates, threshold: int = 50, confidence: int = 95) -> List[TextBlock]:
        res = duplicates
        for textBlock in textBlocks:
            if not textBlock.isPartOfText:
                continue
            zwerg = [textBlock]

            for textBlock2 in textBlocks:

                if not textBlock2.isPartOfText:
                    continue

                if textBlock == textBlock2:
                    continue

                tBlockText1 = re.sub('\W', '', textBlock.text)
                tBlockText2 = re.sub('\W', '', textBlock2.text)

                if tBlockText1 == tBlockText2:
                    zwerg.append(textBlock2)

                elif min(len(tBlockText1) / 2, len(tBlockText2) / 2) < threshold:
                    if fuzz.ratio(tBlockText1[-threshold:], tBlockText2[-threshold:]) > confidence:
                        zwerg.append(textBlock2)
                else:
                    if fuzz.ratio(tBlockText1[:threshold], tBlockText2[:threshold]) > confidence:
                        if fuzz.ratio(tBlockText1[-threshold:], tBlockText2[-threshold:]) > confidence:
                            zwerg.append(textBlock2)

            if len(zwerg) > 1:
                # Deactivate all textBlocks that have the less information (len of text)
                zwerg.sort(key=lambda x: len(x.text), reverse=True)
                for textBlock in zwerg[1:]:
                    textBlock.isPartOfText = False
                    textBlock.isRecurringElement = True
                    res.append(textBlock)
        return res


    def get_geometrical_duplicates(self, textBlocks, duplicates, numberOfRepetions):
        res = duplicates
        zwerg = defaultdict(list)
        for textBlock in textBlocks:
            if textBlock.isPartOfText:
                zwerg[str(textBlock.position)].append(textBlock)
        for textBlocks in zwerg.values():
            if len(textBlocks) > numberOfRepetions:
                # Deactivate all textBlocks
                for textBlock in textBlocks:
                    textBlock.isPartOfText = False
                    textBlock.isRecurringElement = True
                res.extend(textBlocks)
        return res


    def identifyTextOutOfOrder(self, textBlocks, cols: int = 5) -> List['Textblock']:
        """
            Intention:
            The Idea is to say, Text will be always organized in some way.
            E.g.in Papers we have mostly some columns on a page. If a few
            of the identified Blocks are not in this columns, these will be
            in most cases Formulas or no text.
            (X1, Y1)
            *------- -------|
            |------- -------|
            |     ------    |  <- this line will be identified as not a TextBlock
            |------- -------* (X2,Y2)
            :List[Textblock]:
        """
        #cols = self.numberOfCols(textBlocks)
        minX, maxX = self.getMinAndMaxWidth()
        colLength = (maxX-minX)/cols
        zwerg = defaultdict(list)
        relevantTextBlocks = [_ for _ in textBlocks if _.isPartOfText]
        averageCol = len(relevantTextBlocks) / cols
        for textBlock in relevantTextBlocks:
            col = int((textBlock.posX1 - minX)/colLength)
            zwerg[str(col)].append(textBlock)

        for col, textBs in zwerg.items():
            if len(textBs) < averageCol * 0.5:
                for textBlock in relevantTextBlocks:
                    if textBlock in textBs:
                        textBlock.isPartOfText = False
        return textBlocks

    def identifyTextOutOfOrder(self, textBlocks, minX: int, maxX: int, column_length: int = 5, columns: int = 5) -> List['Textblock']:
        """
            Intention:
            The Idea is to say, Text will be always organized in some way.
            E.g.in Papers we have mostly some columns on a page. If a few
            of the identified Blocks are not in this columns, these will be
            in most cases Formulas or no text.
            (X1, Y1)
            *------- -------|
            |------- -------|
            |     ------    |  <- this line will be identified as not a TextBlock
            |------- -------* (X2,Y2)
            :List[Textblock]:
        """
        #cols = self.numberOfCols(textBlocks)

        zwerg = defaultdict(int)
        averageCol = len(textBlocks) / columns
        for textBlock in textBlocks:
            col = int((textBlock.posX1 - minX)/column_length)
            zwerg[col] += 1

        for col, counter in zwerg.items():
            if counter < averageCol * 0.5:
                zwerg[col] = False
            else:
                zwerg[col] = True
        return zwerg

    def get_most_common_text_sizes(self) -> List[int]:
        res = []
        prevOccurences = self.sizes[0][0]
        for size, occurences  in self.sizes:
            if occurences/prevOccurences < 0.6:
                break
            else:
                res.append(size)
                if size > 0:
                    res.append(size - 1)
                res.append(size + 1)
                prevOccurences = occurences
        return res


    def identifyTextByCheckingFontSize(self, textBlocks):
        mostCommonSizes = self.getMostCommonTextSizes()
        relevantTextBlocks = [textBlock for textBlock in textBlocks if textBlock.isPartOfText]
        for textBlock in relevantTextBlocks:
            if textBlock.size not in mostCommonSizes:
                textBlock.isPartOfText = False

        return textBlocks


    def orderText(self):
        """
            Intention:
            The Document will be ordered by the kind of reading in Europe. (left to right, up to down)
            In Papers we have mostly some columns. To get the right order we have to punish the lefter columns.
            We can do it by adding a sidelength to the left column for every column.
        """
        sideLength = self.getSideLength()
        colsize = 5
        minX, maxX = self.getMinAndMaxWidth()
        dis = (maxX - minX) / colsize
        zwerg = {}
        for textBlock in self.textBlocks:
            col = int((textBlock.posX1 - minX) / dis)
            if str(col) not in zwerg:
                zwerg[str(col)] = [textBlock]
            else:
                zwerg[str(col)].append(textBlock)

        for col, textBlocks in zwerg.items():
            col = int(col)
            for textBlock in textBlocks:
                textBlock.absY1 = textBlock.posY1 + col * sideLength + textBlock.pageNum * colsize * sideLength
                textBlock.absY2 = textBlock.absY1 + (textBlock.posY2 - textBlock.posY1)
                textBlock.set_absolute_positions_of_lines()

        res = sorted(self.textBlocks, key=lambda x: x.absY1)
        return res

    def getSideLength(self):
        maxSideLength = 0
        for dataBlock in self.textBlocks:
            if dataBlock.posY2 > maxSideLength:
                maxSideLength = dataBlock.posY2
        return maxSideLength

    def getMinAndMaxWidth(self):
        minX = 99999
        maxX = 0
        for textblock in self.textBlocks:
            if textblock.posX1 < minX:
                minX = textblock.posX1
            if textblock.posX2 > maxX:
                maxX = textblock.posX2
        return minX, maxX

class Header:

    def __init__(self, data: TextBlock = None):
        text = ''
        if isinstance(data, TextBlock):
            text = data.text
        elif isinstance(data, str):
            text = data
        self.text = text

    def to_io(self) -> io.Header:
        return io.Header(**{
            "name": self.text
        })

class Chapter:
    IDCounter = 1
    def __init__(self, textLines: List, text: Text=None):
        self.textLines = textLines
        self.text = text
        self.paragraphs: List[Paragraph] = self.getParagraphs()
        self.textInChapter = "\n".join([_.textInParagraph for _ in self.paragraphs])
        self.id: int = Chapter.IDCounter
        self.header: Header = None
        Chapter.IDCounter += 1

    def to_io(self) -> io.Chapter:
        ''' Creates a Row for the responds model '''
        return io.Chapter(**{
                            "paragraphs": [_.to_io() for _ in self.paragraphs],
                            "header": self.header.to_io() if self.header is not None else None
                             })


    def has_header(self) -> bool:
        return self.header is not None


    def save_as_dict(self):
        res = {#"id": self.id,
               "paragraphs": [_.saveAsDict() for _ in self.paragraphs],
               "header": self.header.text if self.header is not None else '',
               #"chapter": self.text.id
                }
        return res


    def printPrettyChapter(self):
        for num, paragraph in enumerate(self.paragraphs):
            print(40 * "#" + f"Paragraph {str(num)}" + 40 * "#")
            textInParagraph = paragraph.textInParagraph
            lenOfParagraph = len(textInParagraph)
            numberOfChars = 80
            lines = [textInParagraph[i:i+numberOfChars] for i in range(0, lenOfParagraph, numberOfChars)]
            print("\n".join(lines))


    def printChapter(self):
        texts = []
        for num, paragraph in enumerate(self.paragraphs):
            textInParagraph = paragraph.textInParagraph
            texts.append(textInParagraph)
        return texts



    def getParagraphs(self):
        paragraphs = []
        linesForParagraph = []
        # 0.9 for Accepting Tabs
        widthOfALine = 0.95 * self.getWidthOfLine()
        for line in self.textLines:
            isACompleteLine: bool = 0 <= line.posX2 - line.posX1 - widthOfALine
            nextLineIsInLine: bool = self.nextIsInLine(line)
            if isACompleteLine or nextLineIsInLine:
                linesForParagraph.append(line)
            else:
                linesForParagraph.append(line)
                paragraph = Paragraph(linesForParagraph, self)
                paragraphs.append(paragraph)
                linesForParagraph = []
        if len(linesForParagraph) > 0:
            paragraph = Paragraph(linesForParagraph, self)
            paragraphs.append(paragraph)
        return paragraphs


    def nextIsInLine(self, line: 'Line'):
        '''
        Checks if the next Line is part of this line. Necessary Step, because PDFs sucks.
        It checks if the next Line is part of the line and if the textBlock ends if the
        next line is a real line, if these lines are splitted by a "." .
        :param line:
        :return:
        '''
        NORMAL_WIDTH = TextBlock.NORMAL_WIDTH_OF_A_SPACE
        if self.textLines[-1] is line:
            return False

        next = self.textLines[self.textLines.index(line) + 1]

        if 0 <= next.posX1 - line.posX2 <= 2 * NORMAL_WIDTH:
            return True
        if not line.textInLine.lstrip().endswith("."):
            return True
        return False


    def getWidthOfLine(self):
        # Identifies the maximum width of a line
        width = 0
        for line in self.textLines:
            zwerg = int(line.posX2) - int(line.posX1)
            if zwerg > width: width = zwerg
        return width

class Paragraph:
    IDCounter = 1
    def __init__(self, linesForParagraph, chapter: Chapter):
        self.linesForParagraph = linesForParagraph
        self.chapter = chapter
        self.sentences: List[Sentence] = self.getSentences()
        self.textInParagraph = " ".join([_.text for _ in self.sentences])
        self.id: int = Paragraph.IDCounter
        Paragraph.IDCounter += 1

    def to_io(self) -> io.Paragraph:
        return io.Paragraph(**{"sentences": [_.to_io() for _ in self.sentences]})

    def saveAsDict(self):
        res = {#"id": self.id,
               "sentences": [_.saveAsDict() for _ in self.sentences],
               #"text": self.textInParagraph,
               #"chapter" : self.chapter.id
         }
        return res



    def getSentences(self):
        sentences = []
        lines: List[str] = [_.textInLine for _ in self.linesForParagraph]
        text: str = self.joinLines(lines)
        sents: List[str] = self.extractSentences(text)

        for sentence in sents:
            sentences.append(Sentence(sentence, self))
        return sentences

    def extractSentences(self, text):
        sentences = []

        zwerg = split_single(text)
        for num, sentence in enumerate(zwerg):
            sentence = sentence.rstrip()

            if len(sentence) > 0 and len(sentences) > 0:
                if sentences[-1][-1] != "." and num > 0:
                    sentences[-1] += " " + sentence.lstrip()
                    continue
            if len(sentences) > 0 and num > 0:
                if len(sentences[-1]) > 5:
                    if sentences[-1][-6:] == "et al.":
                        sentences[-1] += " " + sentence.lstrip()
                        continue
            sentences.append(sentence)
        return sentences



    def joinLines(self, lines):
        sentences = ""
        for num, line in enumerate(lines):
            line = re.sub(" +", " ", line)
            line = line.lstrip().rstrip()
            if len(line) <= 1:
                continue
            if line[-1] == "-":
                sentences += line[:-1]
            else:
                sentences += line + " "
        return sentences




class Sentence:
    IDCounter = 1
    def __init__(self, sentence, paragraph):
        self.text: str = sentence
        self.paragraph: Paragraph = paragraph
        self.id: int = Sentence.IDCounter
        Sentence.IDCounter += 1

    def to_io(self) -> io.Sentence:
        return io.Sentence(**{"text": self.text})

    def saveAsDict(self):
        return {
            #'id': self.id,
            'sentence': self.text,
            #'paragraph_id': self.paragraph.id
        }



