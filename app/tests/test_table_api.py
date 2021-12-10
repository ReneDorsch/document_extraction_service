from unittest import TestCase
from ..core.extraction_modul.apis import GrobidStrategy, TableStrategy
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

class TestTableStrategy(TestCase):
    def test_process_data(self):
        table_api = TableStrategy()
        for dir, _, files in os.walk('testfiles'):
            for file in files:
                if file.endswith(".pdf"):
                    path = os.path.join(dir, file)
                    results = create_test_setup(path)
                    table_api.process_data(results)
