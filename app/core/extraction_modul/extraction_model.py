from __future__ import annotations
import json

from pydantic import BaseModel, Field
import fitz
from app.core.schemas.datamodels import Document
from app.core.extraction_modul.datamodels.internal_models import *
from app.core.extraction_modul.datamodels.text_models import Text
from app.core.extraction_modul.datamodels.table_models import Table
from app.core.extraction_modul.datamodels.image_models import Image
from app.core.extraction_modul.datamodels.meta_data_models import Metadata
from ..detection_models.text_detection import initalize_pos_model


class PDF_Extraction(BaseModel):
    """ A Dataclass containg all the data """

    path_to_pdf: str
    document: fitz.Document = None
    pages: List[fitz.Page] = []
    textBlocks: List[TextBlock] = Field(default=[])
    numberOfPages: int = -1
    text: Text = None
    tables: List[Table] = []
    images: List[Image] = []
    metadata: Metadata = None
    max_width: int
    max_height: int
    tableDescriptions: List = []

    class Config:
        arbitrary_types_allowed = True  # Allows to use Classes that are not validated

    def to_output_model(self, document_id) -> Document:
        """ Saves the data as an ExtractedData-Object. """

        return Document(metadata=self.metadata.to_io(),
                        text=self.text.to_io(self.metadata),
                        tables=[_.to_io() for _ in self.tables],
                        images=[_.to_io() for _ in self.images],
                        document_id=document_id)

    def to_metadata_model(self, document_id) -> Document:
        return Document(metadata=self.metadata.to_io(),
                        document_id=document_id)

    def to_text_model(self, document_id) -> Document:
        Document(text=self.text.to_io(self.metadata),
                 document_id=document_id)

    def to_table_model(self, document_id) -> Document:
        return Document(tables=[_.to_io() for _ in self.tables],
                        document_id=document_id)

    def to_image_model(self, document_id) -> Document:
        return Document(images=[_.to_io() for _ in self.images],
                        document_id=document_id)

    def to_json(self, path):
        """ Saves the data as a json file. """

        data = {"metainformation": {
            "path_to_pdf": self.pathToPDF,
            "pages": self.numberOfPages
        },
            "metadata": self.metaDataExtractor.saveAsDict(),
            "text": self.textExtractor.saveAsDict(),
            "tables": self.tableExtractor.saveAsDict()
        }
        with open(path, "w") as file:
            file.write(json.dumps(data, indent=4))

    @classmethod
    def read_pdf(cls, path_to_pdf: str) -> PDF_Extraction:
        """
               Reads the PDF and extract the information of it for further processing.
               Here we uses PyMuPDF as the extraction tool. In particulary we use the
               function getTextBlocks, which is a wrapper function of extractBLOCKS()
               Documentation PyMuPDF:
               https://pymupdf.readthedocs.io/en/latest/index.html
                Documentation extractBLOCKS():
               https://pymupdf.readthedocs.io/en/latest/textpage.html#TextPage.extractBLOCKS
               :param pathToPDF: Path To the PDF
               :return: Returns True when it was able to extract the data
       """

        initalize_pos_model(True)
        doc = fitz.open(path_to_pdf)
        pages = [doc[i] for i in range(doc.pageCount)]

        max_width, max_height = PDF_Extraction._get_sizes(pages)
        # Initializes the PDF_Extraction
        extract = cls(path_to_pdf=path_to_pdf,
                      document=doc,
                      pages=pages,
                      numberOfPages=doc.pageCount,
                      max_width=max_width,
                      max_height=max_height,
                      textBlocks=PDF_Extraction._extract_textBlocks(pages, max_width))

        return extract

    @staticmethod
    def _get_sizes(pages) -> Tuple[int, int]:
        """ Identifies the max width and height of a document. """
        max_width: int = 0
        max_height: int = 0

        for pageNum, page in enumerate(pages):
            if page.cropbox.x1 > max_width:
                max_width = page.cropbox.x1

            if page.cropbox.y1 > max_height:
                max_height = page.cropbox.y1

        return int(max_width), int(max_height)

    @staticmethod
    def _extract_textBlocks(pages, max_width) -> List[TextBlock]:
        """ Extracts the textblocks from the pages. """
        res = []

        # Initializes Parameters that will be used for every textblock
        TextBlock.initializeParameters(pages, max_width)

        block_id = 0
        for pageNum, page in enumerate(pages):
            blocks = TextBlock.update_data(page.getText("dict"))
            blocks_raw = TextBlock.update_data(page.getText("rawdict"))

            for num, dataBlock in enumerate(blocks["blocks"]):
                block_id += 1
                # Datablock is a Text
                if dataBlock["type"] == 0:
                    res.append(TextBlock(block_id, pageNum, dataBlock, blocks_raw['blocks'][num]))

        return res
