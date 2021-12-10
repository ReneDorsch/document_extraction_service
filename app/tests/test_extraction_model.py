from unittest import TestCase
from ..core.extraction_modul.apis import GrobidStrategy
from ..core.extraction_modul.extraction_model import PDF_Extraction
from ..core.schemas.datamodel import Document
import os

def create_test_setup(path_to_document: str) -> PDF_Extraction:
    """ Just a helper function to recreate the results of the response of the grobid response. """
    extraction_results = PDF_Extraction(path_to_pdf=path_to_document)
    api = GrobidStrategy(False)
    return extraction_results, api

class TestPDF_Extraction(TestCase):
    def test_as_extracted_data(self):
        for dir, _, files in os.walk('testfiles'):
            for file in files:
                if file.endswith(".pdf"):
                    path = os.path.join(dir, file)
                    extract, api = create_test_setup(path)
                    tei_file = path.replace('.pdf', '.tei')
                    with open(tei_file, "r") as tei:
                        extract.grobid_results = api._reorganize_data(tei)

                    data = extract.to_output_model()
                    self.assertIsInstance(data, Document)
