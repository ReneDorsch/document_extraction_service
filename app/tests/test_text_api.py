from unittest import TestCase

from ..core.extraction_modul.apis import GrobidStrategy, TextStrategy
from ..core.extraction_modul.extraction_model import PDF_Extraction
import os

def create_test_setup(path_to_document: str) -> PDF_Extraction:
    """ Just a helper function to recreate the results of the response of the grobid response. """
    extraction_results = PDF_Extraction.read_pdf(path_to_document)
    api = GrobidStrategy(False)
    tei_file = path_to_document.replace('.pdf', '.tei')
    with open(tei_file, "r") as tei:
        extraction_results.grobid_results = api._reorganize_data(tei)
    return extraction_results

class TestTextStrategy(TestCase):
    def test_process_data(self):
        text_api = TextStrategy()
        for dir, _, files in os.walk('testfiles'):
            for file in files:
                if file.endswith(".pdf"):
                    path = os.path.join(dir, file)
                    results = create_test_setup(path)
                    text_api.process_data(results)


    def test_compare_with_textBlock_1(self):
        """ Tests the comparison function. """
        text_api = TextStrategy()
        path_to_test_files = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'testfiles/additional_test')
        for dir, _, files in os.walk(path_to_test_files):
            for file in files:
                if file.endswith(".pdf"):
                    if "marian" in file:
                        path = os.path.join(dir, file)
                        results = create_test_setup(path)
                        break
        sentences = text_api._get_all_sentences(results)
        sent = None
        for sentence in sentences:
            if "Newly emerging" in sentence.text:
                sent = sentence
                break

       # Here the test begins
        for textblock in results.textBlocks:
            for coordinate in sent.coordinates:
                if coordinate.in_textBlock(textblock):
                    sent.compare_with_textBlock(textblock)

        correct_sentence = " Newly emerging Ti3C2Tx–nanosheets (MXenes) have attracted considerable attention in energy storage, catalysis and, more recently, tribology."
        print(repr(sent.text))
        self.assertTrue(sent.text == correct_sentence)
