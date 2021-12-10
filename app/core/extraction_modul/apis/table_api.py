from ._base_api_ import TransformationStrategy
from ..extraction_model import PDF_Extraction
from app.core.detection_models.table_detection import load_table_detection_model, predict_table_boundaries, in_json
from app.core.extraction_modul.datamodels.table_models import Table, Row, Column
from app.core.config import TMP_DIRECTORY
import os
import fitz

class TableStrategy(TransformationStrategy):
    """ An Agent performing all necessary tasks for the extraction and transformation of the table. """
    TABLE_DETECTION_MODEL = load_table_detection_model()
    def __init__(self):
        super().__init__()

    def preprocess_data(self, data: PDF_Extraction) -> None:
        # Identifies possible Tables
        self.identify_table_descriptions(data)

    def postprocess_data(self, data: PDF_Extraction) -> None:
        self.identify_table_headers(data)

    def process_data(self, data: PDF_Extraction) -> None:
        """ Processes the found tables. """
        # Get the relevant pages
        pages = list(set([textBlock.pageNum for textBlock in data.tableDescriptions]))

        # Identify the boundaries of the tables
        boundaries = []
        for page in pages:
            path = self.page_as_image(data, page)

            boundaries.extend(self.get_boundaries(TableStrategy.TABLE_DETECTION_MODEL,
                                                  path,
                                                  page))


        data.tables = Table.from_boundaries(boundaries,
                                            data.textBlocks,
                                            data.tableDescriptions,
                                            pages,
                                            data.document)

    def identify_table_descriptions(self, data: PDF_Extraction):
        for textBlock in data.textBlocks:
            text = textBlock.text
            text = text.lstrip().lower()
            if text.startswith("tab"):
                data.tableDescriptions.append(textBlock)

    def get_boundaries(self, model, path, page):
        prediction_res = predict_table_boundaries(model, path)
        return in_json(prediction_res, path, page)

    def page_as_image(self, data: PDF_Extraction, page: fitz.Page):

        path_to_image = os.path.join(TMP_DIRECTORY, f"tables/{page}.png")
        doc = data.document
        page = doc.load_page(page)
        pix = page.get_pixmap()
        pix.writePNG(path_to_image)
        return path_to_image


    def identify_table_headers(self, data: PDF_Extraction) -> None:
        """ Identifies the table header """
        for table in data.tables:
            first_column: Column = table.columns[0]
            first_row: Row = table.rows[0]
            row_has_more_words_as_column: bool = first_row.get_number_of_words() > first_column.get_number_of_words()
            if row_has_more_words_as_column:
                first_row.is_table_header = True
                table.rows = table.rows[1:]
                table.header = first_row
            else:
                first_column.is_table_header = True
                table.columns = table.columns[1:]
                table.header = first_column



