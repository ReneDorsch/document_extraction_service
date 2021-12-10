from ..core.extraction_modul.datamodels import *
from ..core.extraction_modul.apis import *
from unittest import TestCase
def _get_all_sentences(grobid_results) -> List[InternalSentence]:


    """ Get a list of all sentences in the document. """
    sentences: List[InternalSentence] = []
    for chapter in grobid_results['text']['chapters']:
        for paragraph in chapter.paragraphs:
            sentences.extend(paragraph.sentences)
    return sentences

class TestInternalParagraph(TestCase):
    def test_check_coordinates(self):
        grobid_api = GrobidStrategy(True)
        path_to_file = "/testFiles/additional_test/j.jmrt.2019.12.072.tei.xml"
        path_to_file = "/logging/input/10_09_2021_08_11_43_619807.tei"
        data = open(path_to_file, "r", encoding='ascii').read()
        grobid_results = grobid_api._debug_process_data(data)
        sentences = _get_all_sentences(grobid_results)


        chapters = grobid_results['text']['chapters']
        for chapter in chapters:
            chapter.set_abs_coordinates(grobid_results['metainformation']['document'])
        for chapter in chapters:
            # for each chapter build a bbox
            for _other_chapter in chapters:
                if chapter.text == _other_chapter.text:
                    continue
                if chapter.has_intersecting_bbox(_other_chapter):
                    chapter.rearange_sentences(_other_chapter)

    def test_check_extract_images(self):
        grobid_api = GrobidStrategy(True)
        path_to_file = "/testFiles/additional_test/j.jmrt.2019.12.072.tei.xml"
        path_to_file = "/logging/input/10_09_2021_08_11_43_619807.tei"
        path_to_pdf = ""
        data = open(path_to_file, "r", encoding='ascii').read()
        grobid_results = grobid_api._debug_process_data(data)
        sentences = _get_all_sentences(grobid_results)


        chapters = grobid_results['text']['chapters']
        for chapter in chapters:
            chapter.set_abs_coordinates(grobid_results['metainformation']['document'])
        for chapter in chapters:
            # for each chapter build a bbox
            for _other_chapter in chapters:
                if chapter.text == _other_chapter.text:
                    continue
                if chapter.has_intersecting_bbox(_other_chapter):
                    chapter.rearange_sentences(_other_chapter)

