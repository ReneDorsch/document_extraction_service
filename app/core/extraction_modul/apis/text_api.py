from collections import defaultdict
import re
from ._base_api_ import TransformationStrategy
from ..extraction_model import PDF_Extraction
import copy
from typing import List, Tuple
from ...detection_models.text_detection import is_grammatically_sentence
from ..datamodels.text_models import Text, Header, Chapter
from ..datamodels.internal_models import TextBlock
from ..datamodels.table_models import Table
from ..datamodels.image_models import Image
from ...extraction_modul.apis.util_functions import is_metadata
import json


class TextStrategy(TransformationStrategy):
    ''' An Agent performing all necessary tasks for the extraction and transformation of the text. '''

    def __init__(self):
        super().__init__()

    def preprocess_data(self, data: PDF_Extraction) -> None:
        ''' Identifies text. '''
        data.text = Text(data.textBlocks,
                         TextBlock.NORMAL_WIDTH_OF_A_SPACE,
                         TextBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES,
                         TextBlock.SIZES,
                         TextBlock.FONTS)

        # Check Inconsistencies in Layout.
        self.identify_text_area(data)

    def postprocess_data(self, data: PDF_Extraction) -> None:
        ''' Nothing to implement here. '''
        self._delete_empty_sentences(data)


    def process_data(self, data: PDF_Extraction) -> None:
        ''' Processes the found text. '''
        # Remove Information from other sources
        self._delete_tables(data)
        self._delete_images(data)
        self._delete_metadata(data)

        # Identify the headers
        self._identify_headers(data)
        self._delete_headers(data)

        # Split the text in chapters, paragraphs, sentences
        chapters = self._split_text(data.text)
        chapters = self._remove_empty_chapters(chapters)
        chapters = self._set_headers(chapters, data.text.headers)

        data.text.chapters = chapters

    def _delete_empty_sentences(self, data):
        """ Deletes empty sentences and check the chapters, paragraphs if these are still necessary. """
        c_zwerg = []
        for chapter in data.text.chapters:
            p_zwerg = []
            for paragraph in chapter.paragraphs:
                s_zwerg = []
                for sentence in paragraph.sentences:
                    if sentence.text.rstrip().lstrip() == "":
                        s_zwerg.append(sentence)

                for sentence in s_zwerg:
                    paragraph.sentences.remove(sentence)
                if len(paragraph.sentences) == 0:
                    p_zwerg.append(paragraph)
            for paragraph in p_zwerg:
                chapter.sentences.remove(paragraph)
            if len(chapter.paragraphs) == 0:
                c_zwerg.append(paragraph)

        for chapter in c_zwerg:
            data.text.chapters.remove(chapter)


    def _get_max_span_size(self, textBlocks) -> Tuple[int, int]:
        minX = 99999
        maxX = 0
        for textblock in textBlocks:
            if textblock.posX1 < minX:
                minX = textblock.posX1
            if textblock.posX2 > maxX:
                maxX = textblock.posX2
        return minX, maxX

    def identify_out_of_order_textpositions(self, textBlocks, minX: int, maxX: int, column_length: int = 5,
                                            columns: int = 5) -> List['Textblock']:
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

        zwerg = defaultdict(int)
        averageCol = len(textBlocks) / columns
        for textBlock in textBlocks:
            col = int((textBlock.posX1 - minX) / column_length)
            zwerg[col] += 1

        for col, counter in zwerg.items():
            if counter < averageCol * 0.5:
                zwerg[col] = False
            else:
                zwerg[col] = True
        return zwerg

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

    def get_normal_width(self, widths):
        # Optimistic
        # Identify the most relevant Tuples
        prevLength = 1
        zwerg = []
        for width, frequency in widths:
            if frequency / prevLength > 0.75:
                zwerg.append(int(width))
                prevLength = frequency
            else:
                break
        return max(zwerg)

    def identify_text_area(self, data):
        ''' Identifies the text by executing a list of rules. '''

        text: Text = data.text
        max_doc_width = data.max_width

        # Sort the text
        tBlocks = text.orderText()

        # Delete/Deactivates information
        duplicates: List[TextBlock] = text.get_delete_duplicates()

        partOfTextTextBlocks = [_ for _ in data.textBlocks if duplicates]
        columns = 5
        minX, maxX = self._get_max_span_size(partOfTextTextBlocks)
        colum_length = (maxX - minX) / columns
        most_common_text_positions = self.identify_out_of_order_textpositions(tBlocks, minX, maxX, colum_length,
                                                                              columns)

        widths = self._get_widths(tBlocks, max_doc_width)
        normal_width = self.get_normal_width(widths)

        most_common_font_sizes = text.get_most_common_text_sizes()
        most_common_font = text.get_most_common_fonts()
        for _idx, tBlock in enumerate(partOfTextTextBlocks):
            # Formatbased rules
            # Checking the fontsize
            has_most_common_size: bool = tBlock.size in most_common_font_sizes
            has_most_common_font: bool = tBlock.font in most_common_font

            is_in_order: bool = most_common_text_positions[int((tBlock.posX1 - minX) / colum_length)]
            has_correct_width: bool = 0.95 <= int(tBlock.posX2 - tBlock.posX1) / int(normal_width) <= 1.05
            is_metadata_: bool = is_metadata(tBlock.text)

            case_1: bool = (has_most_common_font or has_most_common_size) and has_correct_width and not is_metadata_
            case_2: bool = is_in_order and has_correct_width and not is_metadata_
            case_4: bool = (has_most_common_font or has_most_common_size) and is_in_order and not is_metadata_
            case_3: bool = case_1 and case_2

            tBlock.isPartOfText_1 = case_1
            tBlock.isPartOfText_2 = case_2
            tBlock.isPartOfText = case_4

        text.partOfTextTextBlocks = [_ for _ in tBlocks if _.isPartOfText]

    def is_meta_data(self, text: str):
        with open(METADATA_PATTERNS, mode="rb") as read_file:
            metadataPatterns = json.load(read_file)
        for metaData, pattern in metadataPatterns.items():
            res = re.findall(pattern, text.lower())
            if res != []:
                return True
        return False

    def _set_headers(self, chapters: List[Chapter], headers) -> List[Chapter]:
        lineheight: int = TextBlock.SIZES[0][0]  # the most common height of a line
        headers = copy.copy(headers)

        # Look for the header that is next to a chapter
        while (len(headers) > 0):

            header = headers.pop(0)
            bestFit = None
            bestDelta = 99999
            for chapter in chapters:
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
        for chapter in chapters:

            has_header: bool = chapter.has_header()
            if not has_header:
                chapter.header = Header()

        return chapters

    def _remove_empty_chapters(self, chapters: List[Chapter]) -> List[Chapter]:
        """ Removes chapters that contain no full sentence. """
        chapters_to_remove = []
        for chapter in chapters:
            is_sentence: bool = is_grammatically_sentence(chapter.textInChapter)
            if not is_sentence:
                chapters_to_remove.append(chapter)
        for chapter in chapters_to_remove:
            chapters.remove(chapter)
        return chapters

    def _split_text(self, text: Text) -> List[Chapter]:
        text.partOfTextTextBlocks = [_ for _ in text.textBlocks if _.isPartOfText]
        text.partOfTextTextBlocks.sort(key=lambda x: x.absY1)
        lines = []
        previousLinePosY2 = 0
        firstLine = True
        res: List[Chapter] = []
        for textBlock in text.partOfTextTextBlocks:
            for line in textBlock.lines:
                linePosY1 = line.posY1
                if firstLine:
                    lines.append(line)
                    firstLine = False
                    previousLinePosY2 = line.posY2
                    previousFontSizes: List[float] = line.fontSizesInLine
                    previousFonts: List[str] = line.fontsInLine
                    previousLine = line
                    continue

                if text.is_part_of_chapter(line, linePosY1, previousFontSizes, previousFonts, previousLinePosY2,
                                           textBlock, previousLine):
                    lines.append(line)
                else:
                    chapter = Chapter(lines, self)
                    res.append(chapter)
                    lines = [line]

                previousLinePosY2 = line.posY2
                previousFontSizes: List[float] = line.fontSizesInLine
                previousFonts: List[str] = line.fontsInLine
                previousLine = line
        return res

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

    def _identify_headers(self, data: PDF_Extraction):
        ''' Identifies header by rules '''
        tables: List[Table] = data.tables
        images: List[Image] = data.images
        text: Text = data.text
        max_width = data.max_width
        headers: List[TextBlock] = []
        textBlocks: List[TextBlock] = data.textBlocks
        widths = self._get_widths(textBlocks, max_width)
        most_common_width: int = int(widths[0][0])

        for _idx, tBlock in enumerate(textBlocks[1:-1]):
            previous_tBlock = textBlocks[_idx - 1]
            next_tBlock = textBlocks[_idx + 1]

            # Checks for enumeration
            starts_with_number: bool = re.search("^\d", tBlock.text.lstrip()) is not None

            # Checks if the textBlock is before or after an chapter
            # between_two_chapters: bool = self._is_between_two_chapters(tBlock)

            # Checks if it is in front of a longer textblock
            long_textBlock_after_tBlock: bool = len(next_tBlock.lines) > 1

            # Checks for shorter textfragments in a line
            smaller_textBlock: bool = (tBlock.posY2 - tBlock.posY1) <= most_common_width

            # Checks if the textBlock is short
            short_textBlock: bool = len(
                tBlock.text.split(' ')) < 8  # If the Text has less then 20 words it is a possible header
            # Checks some known names
            # has_common_title: bool =
            # Checks if the header has at least three chars
            min_size: bool = len(tBlock.text.replace(' ', '')) > 3

            def _part_of_heuristic_names(tBlock):
                header_names = ["introduction", "conclusion", "references", "results", "discussion", "experiment",
                                "setup", "conflicts of interest", "funding"]
                for word in tBlock.text.split(" "):
                    for typical_header in header_names:
                        if word.lower() in typical_header or typical_header in word.lower():
                            return True
                return False

            contains_common_header_name: bool = _part_of_heuristic_names(tBlock)

            prevEndsWithPoint: bool = re.search("\.$", previous_tBlock.text.rstrip())

            # Checks if it is not a Figure or table
            is_figure: bool = self._is_inside_image(tBlock, images)
            is_table: bool = self._is_inside_table(tBlock, tables)

            is_metadata_: bool = is_metadata(tBlock.text)


            case_1: bool = starts_with_number and smaller_textBlock and long_textBlock_after_tBlock and short_textBlock and not (
                    is_figure or is_table)
            case_2: bool = smaller_textBlock and long_textBlock_after_tBlock and short_textBlock and not (
                    is_figure or is_table)
            case_3: bool = not (is_figure or is_table) and (smaller_textBlock) and (
                    short_textBlock and min_size)
            # case_4: bool = case_3 and (starts_with_number or between_two_chapters) and long_textBlock_after_tBlock

            case: bool = ((starts_with_number and prevEndsWithPoint) or contains_common_header_name) \
                         and short_textBlock \
                         and min_size \
                         and (not (is_figure or is_table or is_metadata_))

            if case:
                headers.append(tBlock)
                tBlock.isHeader = True
        text.headers = headers

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

    def _is_inside_text(self, tBlock, text) -> bool:
        for line in tBlock.lines:
            for chapter in text.chapters:
                if line in chapter.textLines:
                    return True

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

    def _delete_headers(self, data: PDF_Extraction) -> None:
        """ Deletes/Deactivates the headers from the text"""
        for textBlock in data.text.textBlocks:
            if textBlock.isHeader:
                textBlock.isPartOfText = False

    def _delete_tables(self, data: PDF_Extraction) -> None:
        """ Deletes/Deactivates the table information from the text"""

        tables: List[Table] = data.tables
        for table in tables:
            if table.isTable:
                for textblock in table.textBlocks:
                    textblock.isPartOfText = False

                table.descriptionBlock.isPartOfText = False

    def _delete_images(self, data: PDF_Extraction) -> None:
        """ Deletes/Deactivates the image_file information from the text"""
        images: List[Image] = data.images
        for image in images:
            if image.is_image:
                for textBlock in image.textBlocksOfImage:
                    textBlock.isPartOfText = False
                # If the textBlock is inside the image_file
                for textBlock in data.text.textBlocks:
                    if textBlock.pageNum == image.pageNum:
                        if image.posX1 < textBlock.posX1 < image.posX2 and image.posY1 < textBlock.posY1 < image.posY2:
                            textBlock.isPartOfText = False
                        if image.posX1 < textBlock.posX2 < image.posX2 and image.posY1 < textBlock.posY2 < image.posY2:
                            textBlock.isPartOfText = False

    def _delete_metadata(self, data: PDF_Extraction) -> None:
        """ Deletes/Deactivates the metainformation from the text. """
        for textBlock in data.text.textBlocks:
            if textBlock.isPartOfMeta:
                textBlock.isPartOfText = False
