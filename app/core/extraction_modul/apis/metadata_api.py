from ._base_api_ import TransformationStrategy
from ..extraction_model import PDF_Extraction
from ..datamodels.meta_data_models import Metadata, Author, Reference
from ..datamodels.text_models import Header, Chapter
from app.core.extraction_modul.datamodels.internal_models import TextBlock
from ..apis.util_functions import is_metadata
from typing import List, Dict
import re
from crossref.restful import Works


class MetadataStrategy(TransformationStrategy):
    ''' An Agent performing all necessary tasks for the extraction and transformation of the text. '''

    def __init__(self):
        super().__init__()

    def postprocess_data(self, data: PDF_Extraction) -> None:
        pass

    def preprocess_data(self, data: PDF_Extraction) -> None:
        data.metadata = Metadata()

    def process_data(self, data: PDF_Extraction) -> None:
        """ Processes the found text. """
        data.metadata.doi = self.get_doi(data)
        crossref_meta_data = self.get_metadata_from_crossref(data)
        data.metadata.authors = self._getAuthor(crossref_meta_data)
        data.metadata.publisher = self._getPublisher(crossref_meta_data)
        data.metadata.title = self._getTitle(crossref_meta_data)
        data.metadata.subTitle = self._getSubTitle(crossref_meta_data)
        data.metadata.ISSN = self._getISSN(crossref_meta_data)
        data.metadata.journal = self._getJournal(crossref_meta_data)
        data.metadata.references = self._get_references(crossref_meta_data)

        data.metadata.copyright = ""
        data.metadata.abstract = self._get_abstract(data)
        data.metadata.abstractAsString = data.metadata.abstract.textInChapter

    def _get_abstract(self, data: PDF_Extraction) -> str:
        '''
        Identifies the Abstract and returns it.
        The Method will try to identify the abstract first by pure textsearch.
        If nothing has been found it will try to find it with heuristic geometrical
        pattern.
        :return: (str) The Abstract as a string
        '''

        datablocks = self.remove_metainformation_from_datablocks(data)
        tBlock = self.find_abstract_from_search_term(datablocks)
        if tBlock is None:
            abstract = self.find_abstract_from_geometry(data, datablocks)
            abstract.text = data.text
            abstract.header = Header("Abstract")

        else:
            abstract = self._get_abstract_text_blocks(tBlock, datablocks)
            abstract.text = data.text
            abstract.header = Header("Abstract")

        return abstract

    def find_abstract_from_geometry(self, data, dataBlocks: TextBlock) -> TextBlock:
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
              :return Finds the Textblock that is likely to be the Abstract
          """

        textBlocks = data.text.orderText()
        # Get the first textBlock on the first page that is longer as X. words and has the same font as the normal text

        for idx_, textBlock in enumerate(textBlocks):
            first_page: bool = textBlock.pageNum < 2
            has_normal_font: bool = textBlock.get_font() == TextBlock.FONTS[0][0]
            has_normal_size: bool = TextBlock.SIZES[0][0] - 1 <= textBlock.get_size() <= TextBlock.SIZES[0][0] + 1
            is_long: bool = len(textBlock.text) > 80  # the textBlock contains at least 50 chars
            other_metadata: bool = textBlock.isPartOfMeta

            if (has_normal_size or has_normal_font) and is_long and first_page and not other_metadata:
                return self.do_something(idx_, textBlocks)

    def _get_abstract_text_blocks(self, tBlock, datablocks: "TextBlock"):
        for _idx, _tBlock in enumerate(datablocks):
            if tBlock == _tBlock:
                return self.do_something(_idx, datablocks)

    def do_something(self, idx, textBlocks):
        lines = []
        firstLine = True

        for textBlock in textBlocks[idx:]:
            for line in textBlock.lines:
                linePosY1 = line.posY1
                if firstLine:
                    lines.append(line)
                    firstLine = False
                    previousLinePosY2 = line.posY2
                    previousFontSizes: List[float] = line.fontSizesInLine
                    previousFonts: List[str] = line.fontsInLine
                    previousLine = line
                    textBlock.isPartOfMeta = True
                    continue

                if self.isPartOfChapter(line, linePosY1, previousFontSizes, previousFonts, previousLinePosY2, textBlock,
                                        previousLine):
                    lines.append(line)
                    textBlock.isPartOfMeta = True
                else:
                    chapter = Chapter(lines, None)

                    return chapter

                previousLinePosY2 = line.posY2
                previousFontSizes: List[float] = line.fontSizesInLine
                previousFonts: List[str] = line.fontsInLine
                previousLine = line

    def isPartOfChapter(self, line, linePosY1, previousFontSizes, previousFonts, previousLinePosY2, textBlock,
                        previousLine) -> bool:
        only_chapter_name: bool = "abstract" == previousLine.textInLine.lower().rstrip().lstrip()
        normalDistanceBetweenPoints: bool = linePosY1 - previousLinePosY2 <= \
                                            textBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES * 1.25
        sameFont: bool = any([True for font in line.fontsInLine if font in previousFonts])
        sameFontSize: bool = any([True for fontSize in line.fontSizesInLine if fontSize in previousFontSizes])

        if previousLine is not None:
            fullLine: bool = 0.9 <= ((line.posX2 - line.posX1) / (previousLine.posX2 - previousLine.posX1)) <= 1.10
            startsLower: bool = re.search("^[a-z]", line.textInLine.lstrip()) is not None
            prevEndsWithoutPoint: bool = re.search("$\.", previousLine.textInLine.rstrip()) is None

            case_1: bool = (normalDistanceBetweenPoints and (sameFont or sameFontSize))
            case_2: bool = (startsLower and prevEndsWithoutPoint and (sameFont or sameFontSize))
            case_3: bool = fullLine and (sameFont or sameFontSize)
            return case_1 or case_2 or case_3 or only_chapter_name

        return normalDistanceBetweenPoints and (sameFont or sameFontSize)

    def find_abstract_from_search_term(self, datablocks):
        '''
        Identifies the TextBlock that contains the (first part of) the abstract.
        :return: A Tuple (int, TextBlock) The first element of the Tuple contains the
        '''
        for tBlock in datablocks:
            if tBlock.pageNum <= 2:
                text = tBlock.text.lower().replace(" ", "")
                if "abstract" in text:
                    return tBlock
        return None

    def remove_metainformation_from_datablocks(self, data: PDF_Extraction) -> List[TextBlock]:
        def is_in(control, txt):
            if control == '':
                return False
            else:
                return control in txt

        res = []
        for tBlock in data.textBlocks:
            no_author: bool = not any([author.lastname in tBlock.text for author in data.metadata.authors])
            no_publisher: bool = not (is_in(data.metadata.publisher, tBlock.text))
            no_title: bool = not (is_in(data.metadata.title, tBlock.text))
            no_subtitle: bool = not (is_in(data.metadata.subTitle, tBlock.text))
            no_issn: bool = not (is_in(data.metadata.ISSN, tBlock.text))
            no_journal: bool = not (is_in(data.metadata.journal, tBlock.text))
            no_doi: bool = not (is_in(data.metadata.doi, tBlock.text))
            no_recurring_element: bool = not (tBlock.isRecurringElement)
            no_other_meta_data: bool = not (is_metadata(tBlock.text))
            no_reference: bool = not any([ref.title.lower() in tBlock.text.lower() for ref in data.metadata.references])
            if no_author and no_title and no_issn and no_subtitle \
                    and no_journal and no_doi and no_publisher and no_recurring_element and no_reference and no_other_meta_data:
                res.append(tBlock)

            else:
                tBlock.isPartOfMeta = True

        return res

    def get_doi(self, data: PDF_Extraction):
        '''
        doi pattern from: https://www.crossref.org/blog/dois-and-matching-regular-expressions/
        Modified to get also inline doi
        :return:
        '''

        def make_pretty(text):
            text = re.sub('-( |)\n', "", text)  # change newlines with " "
            text = re.sub('\n+', " ", text)  # change newlines with " "
            text = re.sub(' +', " ", text)
            text = re.sub('- ', "", text)
            return text

        doi = ''
        for tBlock in data.textBlocks:
            if tBlock.pageNum <= 2:
                text = make_pretty(tBlock.text) + " "
                for match in re.finditer("10\.\d{4,9}/[-\._;()/:\d\w]+\s", text):
                    potDOI = text[match.start():match.end()]
                    if len(potDOI) > len(doi):
                        doi = potDOI
                    break
        return doi.rstrip().lstrip()

    def get_metadata_from_crossref(self, data: PDF_Extraction) -> List:
        '''
        for more information on the used library look at: https://github.com/CrossRef/rest-api-doc
        Here is a quick example of the usage: https://github.com/CrossRef/rest-api-doc/blob/master/demos/crossref-api-demo.ipynb
        :return:
        '''
        worker = Works()
        metadata = data.metadata
        meta = ""
        doi = metadata.doi
        if doi != "":
            try:
                meta = worker.doi(doi)
            except:
                meta = None
        return meta

    def _getAuthor(self, crossref_meta_data):
        res = []
        try:
            for author in crossref_meta_data['author']:
                first_name = author['given'] if 'given' in author else 'NOT_AVAILABLE'
                last_name = author['family'] if 'family' in author else 'NOT_AVAILABLE'
                res.append(Author(firstname=first_name, lastname=last_name))
        except Exception:
            pass
        return res

    def _getTitle(self, crossref_meta_data):
        cross_ref = ''
        try:
            cross_ref = crossref_meta_data['title'][0]
        except Exception:
            pass
        return cross_ref

    def _getSubTitle(self, crossref_meta_data):
        subtitle = ""
        try:
            subtitle = crossref_meta_data['subtitle'][0]
        except Exception:
            pass
        return subtitle

    def _getISSN(self, crossref_meta_data):
        issn: str = ''
        try:
            issn = crossref_meta_data['ISSN'][0]
        except Exception:
            pass
        return issn

    def _getPublisher(self, crossref_meta_data):
        publisher: str = ''
        try:
            publisher = crossref_meta_data['publisher']
        except Exception:
            pass
        return publisher

    def _getJournal(self, crossref_meta_data):
        journal: str = ''
        try:
            journal = crossref_meta_data['container-title'][0]
        except Exception:
            pass
        return journal

    def _get_references(self, crossref_meta_data):
        res: List[Reference] = []
        try:
            references = crossref_meta_data['reference']
            for ref in references:
                doi = ref['DOI']
                author = ref['author'] if 'author' in ref else 'NOT_AVAILABLE'
                title = ref['article-title'] if 'article-title' in ref else 'NOT_AVAILABLE'
                res.append(Reference(doi, author, title))
        except Exception:
            pass
        return res
