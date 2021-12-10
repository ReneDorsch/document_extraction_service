from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Union


class InputDocument(BaseModel):
    file: str = Field(description="The PDF-Document as an bytearray encoded with the urlsafe_b64decode algorithmn. "
                                  "For further information on this encoding see: https://docs.python.org/3/library/base64.html")
    document_id: str = Field(description="An ID that helps to uniquely identify a document. ")


class ResponseDocument(BaseModel):
    document_id: str = Field(description="An ID that helps to uniquely identify a document. ")
    metadata: MetaData = Field(description='Metadata identified by analysing the pdf-document.')
    text: Text = Field(description="The extracted textinformation of the document. ")
    tables: List[Table] = Field(description="A list of tables extracted from the document. ")
    images: List[Image] = Field(description="A list of images extracted from the document. ")


class Text(BaseModel):
    chapters: List[Chapter] = Field(description="The identified chapters from the document. ")
    abstract: Chapter = Field(default=None)
    title: str = Field(default="")
    authors: List[Author] = Field(default=[])


class Chapter(BaseModel):
    paragraphs: List[Paragraph] = Field(description="A list of paragraphs identified for this chapter. ")
    header: Header = Field(default=None, description="The Header for this chapter. ")


class Header(BaseModel):
    name: str


class Paragraph(BaseModel):
    sentences: List[Sentence] = Field(description="A list of sentences identified for this chapter. ")


class Sentence(BaseModel):
    text: str = Field(description="The text from this sentence")


class MetaData(BaseModel):
    abstract: Chapter = Field(default=None)
    references: List[Reference] = Field(default=[])
    issn: str = Field(default="")
    journal: str = Field(default="")
    title: str = Field(default="")
    subtitle: str = Field(default="")
    publisher: str = Field(default="")
    authors: List[Author] = Field(default=[])
    doi: str = Field(default="")


class Reference(BaseModel):
    doi: str = Field(default='')
    authors: List[Author] = Field(default=[],
                                  description="A Reference that was mentioned in the text. E.g. a citation. ")
    title: str = Field(description='A Title of an reference.')


class Author(BaseModel):
    first_name: str
    last_name: str


class Image(BaseModel):
    base64_file: str = Field(description="The image_file in an base64 format.")
    description: str
    name: str


class Table(BaseModel):
    rows: List[Row] = Field(description="A list of rows for the table. ")
    columns: List[Column] = Field(description="A list of columns for the table. ")
    description: str = Field(default="The description of the table. ")
    name: str = Field(description="The name of the table. ")
    base64_file: str = Field(description="Image of the Table as a base64 encoded file. ")
    table_header: Union[Column, Row] = Field(description="A Line that corresponds to the header.")



class Line(BaseModel):
    cells: List[Cell] = Field(description="A list of cells at their position in the Line ")


class Row(Line):
    cells: List[Cell] = Field(description="A list of Cells in the row. ")


class Column(Line):
    ells: List[Cell] = Field(description="A list of Cells in the column. ")


class Cell(BaseModel):
    text: str
    category: str
    type: str


Paragraph.update_forward_refs()
Chapter.update_forward_refs()
Text.update_forward_refs()

Column.update_forward_refs()
Row.update_forward_refs()
Table.update_forward_refs()

Image.update_forward_refs()

MetaData.update_forward_refs()
ResponseDocument.update_forward_refs()

Reference.update_forward_refs()