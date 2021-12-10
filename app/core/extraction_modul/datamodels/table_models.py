from __future__ import annotations

import copy
import math
from collections import defaultdict
from typing import List, Type, Tuple, Dict, Union
import spacy
import re
import fitz
import os

from app.core.detection_models.text_detection import is_grammatically_sentence, get_type_frequency
from PIL import Image
import base64
from app.core.detection_models import table_detection
from app.core.extraction_modul.datamodels.internal_models import TextBlock, Line
import app.core.schemas.datamodels as io
from app.core.config import TMP_DIRECTORY


class Table:
    IDCounter = 0

    def __init__(self, tableDescription, textBlocks, x1, y1, x2, y2):
        """
        docstring
        """
        self.pageNum = tableDescription.pageNum
        self.descriptionBlock = tableDescription
        self.textBlocksOfTable = []
        self.textBlocks = textBlocks
        self.posX1 = x1
        self.posY1 = y1
        self.posX2 = x2
        self.posY2 = y2
        self.rows: List[Row] = []
        self.numberOfRows = 0
        self.numberOfCols = 0
        self.cells: Cell = []
        self.isTable: bool = True
        self.id: int = Table.IDCounter
        self.header: Union[Row, Column] = None
        self.path_to_image: str = ''
        self.image_file = b""
        Table.IDCounter += 1

        # Updates the textBlock information
        tableDescription.isPartOfTable = True
        for textBlock in textBlocks:
            textBlock.isPartOfTable = True

    def get_table_name(self) -> str:
        ''' Gets the name of the table. '''
        table_name = ""
        text: str = self.descriptionBlock.text
        if self.descriptionBlock is not None:
            match = re.search("^tab(\.|le) +\d+", text.lower())
            table_name = text[match.start(): match.end()]
        return table_name

    def get_image_as_base64_file(self) -> str:
        """ Returns the image file in base64 encoded format """
        return base64.urlsafe_b64encode(self.image_file).encode('utf-8')

    def to_io(self) -> io.Table:
        ''' Creates a Table for the response model'''
        description = self.descriptionBlock.text
        name = self.get_table_name()
        file = base64.urlsafe_b64encode(self.image_file).decode('utf-8')
        header = self.header
        return io.Table(**{
            "rows": [_.to_io() for _ in self.rows],
            "columns": [_.to_io() for _ in self.columns],
            "description": description,
            "name": name,
            "base64_file": file,
            "table_header": header.to_io() if header is not None else None
        })

    def _create_image(self, pageNum: int, fitz_doc) -> None:

        path_to_image = os.path.join(TMP_DIRECTORY, f"tables/{pageNum}_{self.posX2}_{self.posX1}_{self.posY2}_{self.posY1}.png")

        clip = fitz.Rect(self.posX1, self.posY1, self.posX2, self.posY2)
        page = fitz_doc.load_page(pageNum)
        pix = page.get_pixmap(clip=clip)

        pix.writePNG(path_to_image)
        self.path_to_image = path_to_image
        self.image_file = open(path_to_image, "rb").read()

    @classmethod
    def from_boundaries(cls, boundaries: Dict, textBlocks: List[TextBlock], tableDescriptions: List[TextBlock], pages,
                        fitz_doc: str) -> List[Table]:

        def average_height(textBlocks: List[TextBlock]) -> float:
            ''' Helper function to calculate the average height of a list of textBlocks. '''

            return sum([_.size for _ in textBlocks]) / len(textBlocks)

        res: List[Table] = []
        _tableDescription = copy.copy(tableDescriptions)
        for boundary in boundaries:
            tableData: List[TextBlock] = []
            # Find the next tableDescription
            descriptions = [tDescription for tDescription in _tableDescription if
                            tDescription.pageNum == boundary['page']]
            # If no description could be found go to the next table
            if len(descriptions) == 0:
                continue

            bestFit: TextBlock = descriptions[0]
            for description in descriptions[1:]:
                prevDist1 = ((bestFit.posX2 - boundary['x2']) ** 2 + (bestFit.posY1 - boundary['y1']) ** 2) ** (1 / 2)
                prevDist2 = ((bestFit.posX2 - boundary['x2']) ** 2 + (bestFit.posY2 - boundary['y2']) ** 2) ** (1 / 2)
                prevDist3 = ((bestFit.posX1 - boundary['x1']) ** 2 + (bestFit.posY1 - boundary['y1']) ** 2) ** (1 / 2)
                prevDist4 = ((bestFit.posX1 - boundary['x1']) ** 2 + (bestFit.posY2 - boundary['y2']) ** 2) ** (1 / 2)
                prevDistance = min([prevDist1, prevDist2, prevDist3, prevDist4])

                prevDist1 = ((description.posX2 - boundary['x2']) ** 2 + (description.posY1 - boundary['y1']) ** 2) ** (
                        1 / 2)
                prevDist2 = ((description.posX2 - boundary['x2']) ** 2 + (description.posY2 - boundary['y2']) ** 2) ** (
                        1 / 2)
                prevDist3 = ((description.posX1 - boundary['x1']) ** 2 + (description.posY1 - boundary['y1']) ** 2) ** (
                        1 / 2)
                prevDist4 = ((description.posX1 - boundary['x1']) ** 2 + (description.posY2 - boundary['y2']) ** 2) ** (
                        1 / 2)
                distance = min([prevDist1, prevDist2, prevDist3, prevDist4])

                if prevDistance > distance:
                    bestFit = description

            _tableDescription.remove(bestFit)

            # Find the textBlocks inside the boundary
            for textBlock in textBlocks:
                if textBlock.is_part_of(boundary['page'], boundary["x1"], boundary["y1"], boundary["x2"],
                                        boundary["y2"]):
                    tableData.append(textBlock)

            # Identify the number of Rows
            height = boundary['y2'] - boundary['y1']

            # Create a Table
            table = cls(bestFit, tableData, boundary["x1"], boundary["y1"], boundary["x2"], boundary["y2"])
            table.create_rows()
            table.create_cells()
            table.setColumns(boundary["x1"], boundary["y1"], boundary["x2"], boundary["y2"])
            table.update_cell_positions()
            table._create_image(boundary['page'], fitz_doc)
            res.append(table)

        return res

    def create_cells(self):
        cells = []
        for row in self.rows:
            row.set_cells()
            cells.extend(row.cells)
        self.cells = cells

    def create_rows(self, height) -> None:
        # Get the line with the max. number of rows
        max_number_of_rows = height / TextBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES
        # Get the lines
        lines = []
        for tBlock in self.textBlocks:
            lines.extend(tBlock.lines)
            tBlock.isPartOfTable = True

        # Sort the textBlocks
        lines.sort(key=lambda x: x.posY1)

        # Create new rows and update them
        rows = []
        for num, line in enumerate(lines):
            row = Row.from_line(line, num, self)
            rows.append(row)

        self.rows = rows

    def create_rows(self) -> None:

        # Get the lines
        lines = []
        for tBlock in self.textBlocks:
            lines.extend(tBlock.lines)
            tBlock.isPartOfTable = True

        # Sort the textBlocks
        lines.sort(key=lambda x: x.posY1)

        # Create new rows and update them
        rows = []
        for num, line in enumerate(lines):
            row = Row.from_line(line, num, self)
            row.set_cells()
            rows.append(row)

        self.rows = rows

    def is_inside(self, tBlock) -> bool:
        if tBlock.pageNum == self.pageNum:
            if self.posY1 <= tBlock.posY1 <= self.posY2 or self.posY1 <= tBlock.posY2 <= self.posY2:
                if self.posX1 <= tBlock.posX1 <= self.posX2 or self.posX1 <= tBlock.posX2 <= self.posX2:
                    return True
        return False

    def saveAsDict(self):

        with open(self.path_to_image, "rb") as image_file:
            encoded_img_string = base64.urlsafe_b64encode(image_file.read()).decode('utf-8')

        row_size = max([len(_.cells) for _ in self.rows])
        rows_ = []
        for _ in self.rows:
            if _.is_row:
                res = _.saveAsDict(row_size)
                rows_.append(res)
        res = {
            # "id": self.id,
            "rows": rows_,
            "header": self.save_header_as_string(),
            "image_base64": encoded_img_string
            # "page": self.pageNum
        }

        return res

    def save_header_as_string(self) -> str:

        return self.descriptionBlock.text

    def setLabelAndDataCells(self):
        '''
        Identifies Labels in the Table by
        :return:
        '''
        # The labels are always Words
        # The Datas can be both, words and Num
        first_row = self.rows[0]
        first_col = self.columns[0]

        categoriesPerRow = self._getCategoriesPerLine(self.rows, True)
        categoriesPerColumn = self._getCategoriesPerLine(self.columns, False)

        # categories = [set(row) for row in categoriesPerRow]
        # variationPerRow = [row.count(category) for category in categories for row in categoriesPerRow]
        # categories = [set(col) for col in categoriesPerColumn]
        # variationPerColumn= [row.count(category) for category in categories for row in categoriesPerRow]
        # print("OK")

    def _getCategoriesPerLine(self, lines, isRow: bool):
        if isRow:
            lines = [_.cells for _ in lines if not _.isHeader]
        zwerg = {}
        for line in lines:
            if "UNKNOWN" in line: continue
            categories = [_.mostCommonTypeOfWord for _ in line]
            if str(categories) not in zwerg:
                zwerg[str(categories)] = 1
            else:
                zwerg[str(categories)] += 1
        return zwerg

    def __is_in_col(self, m_cell, cell, row):
        if row.orientation == 0:
            # If the centers are in a line
            if m_cell.centerX * 0.95 <= cell.centerX <= m_cell.centerX * 1.05:
                return True
            # if it is right oriented
            if m_cell.posX1 <= cell.posX1 <= m_cell.posX2:
                return True
        else:
            # If the centers are in a line
            if int(m_cell.centerY) * 0.95 <= cell.centerY <= int(m_cell.centerY) * 1.05:
                return True
            # if it is right oriented
            if m_cell.posY1 <= cell.posY2 <= m_cell.posY2:
                return True
        return False

    def _set_matrix(self) -> None:

        # Idea description
        # Problemdescription
        # Right now, we have a table that (maybe) looks like this:
        # | cell_1_1 | cell_1_2 | cell_1_3 |
        # | cell_2_1 | cell_2_2 |
        #      | cell_3_1 | cell_3_2 | cell_3_3 |
        #  | cell_4_1         | cell_4_3 |
        # | cell_5_1 | cell_5_2 | cell_5_3 | cell_5_3 |
        # Strategy
        # The first thing to do, is to identify the maximum length of a row
        # We have already the number of rows, so we dont need them to
        # After that we split our table in n rows, where n is the maximum number of elements in a row
        # Then we assign every cell in a row a place in our grid
        # For this we can use the minimum distance to a gridelement
        # After that we will fill our grid with empty elements
        _rows: List[Row] = [row for row in self.rows if row.is_row]
        if len(_rows) < 1:
            return

        _max_number_of_cells: int = max([len(_.cells) for _ in _rows])
        # if its horizontal
        if _rows[0].orientation == 0:
            _min = min([_.posX1 for _ in _rows])
            _max_length_of_row = max([_.posX2 for _ in _rows]) - _min
        # if its vertical
        else:
            _min = min([_.posY1 for _ in _rows])
            _max_length_of_row = max([_.posY2 for _ in _rows]) - _min

        _cell_size = _max_length_of_row / _max_number_of_cells
        _centers_of_rows = []
        for _cell_number in range(0, (_max_number_of_cells)):
            _centers_of_rows.append((_min + _cell_number * _cell_size + 0.5 * _cell_size))

        for row in _rows:
            _row_postions_in_use: List[bool] = [False] * _max_number_of_cells
            _cells: List[Cell] = [None] * _max_number_of_cells
            for cell in row.cells:
                min_distance = 9999
                cell_number = -1
                for _cell_number, cell_position in enumerate(_centers_of_rows):
                    if not _row_postions_in_use[_cell_number]:
                        if _rows[0].orientation == 0:
                            distance = abs(cell.centerX - cell_position)
                        else:
                            distance = abs(cell.centerY - cell_position)
                        if distance < min_distance:
                            cell_number = _cell_number
                            min_distance = distance
                _row_postions_in_use[cell_number] = True
                _cells[cell_number] = cell

            while None in _cells:
                _idx: int = _cells.index(None)

                if _rows[0].orientation == 0:
                    position = (_centers_of_rows[_idx] - 0.5 * _cell_size, row.cells[0].posY1,
                                _centers_of_rows[_idx] + 0.5 * _cell_size, row.cells[0].posY2)
                else:
                    position = (row.cells[0].posX1, _centers_of_rows[_idx] - 0.5 * _cell_size,
                                row.cells[0].posX2, _centers_of_rows[_idx] + 0.5 * _cell_size)

                _cells[_idx] = Cell(position, " ")

            row.cells = _cells

    def _set_columns(self):
        _rows: List[Row] = self.rows
        if len(_rows) < 1:
            return

        _cols = [[] for _ in range(max([len(row.cells) for row in _rows]))]

        for row in _rows:
            for _col_number in range(0, len(_cols)):
                _cols[_col_number].append(row.cells[_col_number])

        self.columns = _cols

    def setColumns(self):

        # To-Do:
        # test table Extraction again
        # with document s40544-....
        _rows = [row for row in self.rows]
        _rows.sort(key=lambda row: row.numberOfCols, reverse=True)
        row_with_max_cols = _rows[0]
        # Get the center of the cells
        cols = {}
        for cell in row_with_max_cols.cells:
            # If row is horizontal
            if row_with_max_cols.orientation == 0:
                cols[str(int(cell.centerX))] = [cell]
            # If row is vertical
            else:
                cols[str(int(cell.centerY))] = [cell]

        for row in self.rows:
            if row is not row_with_max_cols:
                for cell_position, cells in cols.items():
                    found_cell = False
                    if len(row.cells) < len(cols):
                        while (len(row.cells) < len(cols) and not found_cell):
                            # If length of the row is smaller as the cols
                            for cell in row.cells:
                                if self.__is_in_col(cells[0], cell, row):
                                    cols[cell_position].append(cell)
                                    found_cell = True
                                    break
                            # If no cell was found add a new cell (so we get a grid)
                            if not found_cell:
                                if row_with_max_cols.orientation == 0:
                                    cell = Cell((int(cell_position), row.posY1, int(cell_position), row.posY2), " ")
                                    row.cells.append(cell)
                                    cols[cell_position].append(cell)
                                else:
                                    cell = Cell((row.posX1, int(cell_position), row.posX2, int(cell_position)), " ")
                                    row.cells.append(cell)
                                    cols[cell_position].append(cell)
                    # Set the next cell to the col
                    else:
                        next_cell = None
                        min_distance = 9999
                        for cell in row.cells:
                            if row_with_max_cols.orientation == 0:
                                distance = (abs(int(cell_position) ** 2 - cell.centerX ** 2)) ** (1 / 2)
                            else:
                                distance = (abs(int(cell_position) ** 2 - cell.centerY ** 2)) ** (1 / 2)
                            if distance < min_distance:
                                next_cell = cell
                                min_distance = distance
                        cols[cell_position].append(next_cell)

        self.columns = cols

    def setColumns(self, x1, x2, y1, y2):

        def get_rows():
            zwerg = []
            for row in self.rows:
                zwerg.extend(row.cells)
            rows = []
            while (len(zwerg) > 0):
                cell = zwerg.pop(0)
                rows.append(cell)
                to_remove = []
                counter = 1
                while (counter != 0):
                    counter = 0
                    for _cell in zwerg:
                        if _cell not in to_remove:
                            delta_1 = cell.posX2 - cell.posX1
                            delta_2 = _cell.posX2 - _cell.posX1
                            if delta_2 > delta_1:
                                if _cell.posX1 <= cell.centerX <= _cell.posX2:
                                    to_remove.append(_cell)
                                    counter += 1
                            else:
                                if cell.posX1 <= _cell.centerX <= cell.posX2:
                                    rows.remove(cell)
                                    rows.append(_cell)
                                    cell = _cell
                                    to_remove.append(_cell)
                                    counter += 1
                for cell in to_remove:
                    if cell in zwerg:
                        zwerg.remove(cell)
            return rows

        width = x2 - x1

        rows = get_rows()
        rows.sort(key=lambda x: x.posX1)
        max_cols = max([row.numberOfCols for row in self.rows])

        width_of_a_column = math.ceil(width / (max_cols - 1))
        res = []

        for num, row in enumerate(rows):
            res.append(Column(num, row.posX1, row.posX2, y1, y2, self))

        self.columns = res

    def reorder_rows(self):
        self.rows.sort(key=lambda x: x.posY1)
        print("ok")

    def reorder_cols(self):
        print("ok")

    def update_cell_positions(self):
        class container:
            def __init__(self, x1, x2, y1, y2, row, column):
                self.x1 = x1
                self.x2 = x2
                self.y1 = y1
                self.y2 = y2
                self.centerX = x1 + (x2 - x1) / 2
                self.centerY = y1 + (y2 - y1) / 2
                self.row = row
                self.column = column
                self.distances = {}

        # get all cells
        zwerg = []
        zwerg_2 = []
        # calculate for each cell the distance to all row-column-cells
        for row in self.rows:
            for column in self.columns:
                zwerg_2.append(container(column.posX1, column.posX2, row.posY1, row.posY2, row, column))

        for cell in self.cells:
            cell.distances = {}
            for c in zwerg_2:
                cell.distances[c] = ((cell.centerX - c.centerX) ** 2 + (cell.centerY - c.centerY) ** 2) ** (1 / 2)

        new_rows = []
        for row in self.rows:
            new_row = Row(row.rowNumber, line=None, table=row.table)
            new_row.posY2 = row.posY2
            new_row.posY1 = row.posY1
            new_row.posX1 = row.posX1
            new_row.posX2 = row.posX2
            new_rows.append(new_row)
            for column in self.columns:
                new_row.cells.append(Cell((column.posX1, row.posY1, column.posX2, row.posY2), " ", row, None))

        def get_cell_with_smallest_distance():
            zwerg = []
            for cell in self.cells:
                if cell.not_activated:
                    options = []
                    for key, distance in cell.distances.items():
                        options.append((distance, key, cell))

                    options.sort(key=lambda x: x[0])
                    zwerg.append(options[0])

            zwerg.sort(key=lambda x: x[0])
            return zwerg[0][1], zwerg[0][2]

        # Get the cell that is next to a given cell_container
        while (any([_.not_activated for _ in self.cells])):
            key, cell = get_cell_with_smallest_distance()
            for row in new_rows:
                for _cell in row.cells:
                    if _cell.posX1 <= key.centerX <= _cell.posX2 and _cell.posY1 <= key.centerY <= _cell.posY2:
                        _cell.text = cell.text
                        _cell.mostCommonTypeOfWord = cell.mostCommonTypeOfWord
                        _cell.numberOfWords = cell.numberOfWords
                        cell.not_activated = False

        # Save the rows
        self.rows = new_rows

        # Update the position of the columns:
        for num, column in enumerate(self.columns):
            for row in self.rows:
                column.cells.append(row.cells[num])

        print("ok")
        # Calculate the error for the complete table

    def do_magic(self):

        class c:
            def __init__(self, x1, x2, y1, y2, row, column):
                self.x1 = x1
                self.x2 = x2
                self.y1 = y1
                self.y2 = y2
                self.centerX = x1 + (x2 - x1) / 2
                self.centerY = y1 + (y2 - y1) / 2
                self.row = row
                self.column = column
                self.distances = {}

        # number of cells
        n_cells = len(self.rows) * len(self.columns)
        new_cells = n_cells - len(self.cells)

        # Coordinates of the columns

        # Coordinates of the rows

        # In each row look if there is some empty place in a row
        # if it is the case add there an additional cell.
        for row in self.rows:
            new_cells = []
            if len(row.cells) < len(self.columns):
                for column in self.columns:
                    cell_found = False
                    for cell in row.cells:
                        if cell.column == column:
                            cell_found = True
                    if not cell_found:
                        new_cells.append(Cell((column.posX1, row.posY1, column.posX2, row.posY2), " ", row))
            row.cells.extend(new_cells)
        print("ok")

    def setHeader(self):
        # To-Do:
        # Check if something is above or under the header,
        # If the rows below or above contains a lot empty cells
        # delete them from the table
        for row in self.rows:
            if row.getRowAsString().lower().startswith("tab"):
                row.isHeader = True
                self.header.append(row)
        # Rows between the first real row and the header are part of the header
        if len(self.header) > 0:
            header = self.header[0]
            # if horizont
            if header.orientation == 0:
                first_row = None
                for row in self.rows:
                    if row.is_row:
                        if first_row is None:
                            first_row = row
                        else:
                            if abs(first_row.posY1 - header.posY2) > abs(row.posY1 - header.posY2):
                                first_row = row
                if first_row is not None:
                    for row in self.rows:
                        if abs(row.posY2 - header.posY2) < abs(first_row.posY2 - header.posY2):
                            if row not in self.header:
                                self.header.append(row)
            # Case the table is vertical oriented
            else:
                first_row = None
                for row in self.rows:
                    if row.is_row:
                        if first_row is None:
                            first_row = row
                        else:
                            if abs(first_row.posX1 - header.posX2) > abs(row.posX1 - header.posX2):
                                first_row = row
                if first_row is not None:
                    for row in self.rows:
                        if abs(row.posX2 - header.posX2) < abs(first_row.posX2 - header.posX2):
                            if row not in self.header:
                                self.header.append(row)

        # Delete all rows that are not part of the table.
        for row in self.rows:

            if not row.is_row:
                for line in row.rowInformation:
                    for datablock in self.textBlocks:
                        if line in datablock.lines:
                            datablock.isPartOfTable = False

    def _countRows(self):
        # Not longer used
        zwerg = {}
        for row in self.rows:
            if not row.isHeader:
                if str(row.numberOfCols) not in zwerg:
                    zwerg[str(row.numberOfCols)] = [row]
                else:
                    zwerg[str(row.numberOfCols)].append(row)
        zwerg = [(int(numberOfCols), rows) for numberOfCols, rows in zwerg.items()]
        zwerg.sort(key=lambda x: len(x[1]), reverse=True)
        return zwerg

    def printTable(self):
        # Not longer used
        # But maybe it should
        for row in self.rows:
            line = ""
            if row.isHeader:
                for cell in row.cells:
                    line += " " + cell.text
            else:
                for cell in row.cells:
                    line += "\t|\t" + cell.text
            print(line)

    def getDataForCamelot(self):
        # not longer used
        posX1 = 9999
        posY1 = 9999
        posX2 = -9999
        posY2 = -9999
        for row in self.rows:
            x1, y1, x2, y2 = self._getPositionOfTable(self.descriptionBlock, row)
            posX1 = posX1 if posX1 <= x1 else x1
            posY1 = posY1 if posY1 <= y1 else y1
            posX2 = posX2 if posX2 > x2 else x2
            posY2 = posY2 if posY2 > y2 else y2
        return posX1, posY1, posX2, posY2, self.pageNum

    def getTextBlocksInTable(self, textBlocks):

        res = []
        posX1, posY1, posX2, posY2, self.pageNum = self.getDataForCamelot()
        zwerg = []
        for textBlock in textBlocks['blocks']:
            if 'lines' in textBlock.keys():
                for line in textBlock['lines']:
                    for span in line['spans']:
                        for char in span['chars']:
                            zwerg.append(char)
        for word in zwerg:
            # if int(word[0]) >= posX1 and int(word[2]) <= posX2:
            #     if int(word[1]) >= posY1 and int(word[3]) <= posY2:
            #         res.append(word)
            if int(word['bbox'][0]) >= posX1 and int(word['bbox'][2]) <= posX2:
                if int(word['bbox'][1]) >= posY1 and int(word['bbox'][3]) <= posY2:
                    res.append(word)
        return res

    def createNewPdf(self, path):
        doc2 = fitz.open(path)
        doc = fitz.open()
        page = doc.newPage()
        page_rect = page.rect
        black = (0, 0, 0)
        # writer = fitz.TextWriter(page_rect, color=black)  # start a text writer

        page2 = doc2[self.pageNum]
        textBlocks = self.getTextBlocksInTable(page2.getText("rawdict"))

        for textBlock in textBlocks:
            fill_rect = fitz.Rect(textBlock['bbox'][0], textBlock['bbox'][1], textBlock['bbox'][2],
                                  textBlock['bbox'][3])
            text = textBlock['c']

            shape = page.newShape()
            shape.insertTextbox(rect=fill_rect, buffer=text, fontsize=6, color=black)
            # writer.fillTextbox(  # fill in above text
            #     fill_rect,  # keep text inside this
            #     text,  # the text
            #     warn=True,
            # )
            shape.commit()
        # write our results to the PDF page.
        # writer.writeText(page)

        doc.save(f"testFiles/example{str(self.id)}.pdf")

    def wordsPerElement(self):
        textLengthOfTable = " "
        for tBlock in self.textBlocksOfTable:
            textLengthOfTable += " " + tBlock.text
        return len(textLengthOfTable.split(" "))

    def numberOfSentencesInTable(self):
        counter = 0
        relevant_rows = [row for row in self.rows if row.is_row]
        text_in_rows = [_.rowInformation[0].textInLine for _ in relevant_rows]
        for text in text_in_rows:
            if is_grammatically_sentence(text):
                counter += 1
        return counter

    def averageNumberOfElementsInRow(self) -> float:
        numberOfElementsInTable = 0
        relevant_rows = [row for row in self.rows if row.is_row]
        if len(relevant_rows) == 0:
            return 0
        for row in relevant_rows:
            numberOfElementsInTable += row.numberOfCols
        averageNumberOfElementsInRow = numberOfElementsInTable / len(relevant_rows)
        return averageNumberOfElementsInRow

    def getOrientation(self, textBlock):
        return textBlock.orientation

    def getSpaceBetweenTwoLines(self, orientation, firstTextBlock, secondTextBlock):
        distanceBetweenTwoRows: int = 9999
        # Horizontal Oriented TextBlock
        if orientation == 0 or orientation == 2:
            for lineDescriptionBlock in secondTextBlock.lines:
                for lineRowDescriptionBlock in firstTextBlock.lines:
                    posY1OfDescriptionBlock = lineDescriptionBlock.posY1
                    posY2OfDescriptionBlock = lineDescriptionBlock.posY2
                    posY1OfRowDescriptionBlock = lineRowDescriptionBlock.posY1
                    posY2OfRowDescriptionBlock = lineRowDescriptionBlock.posY2
                    # Considering centric elements
                    distance = min([abs(posY2OfRowDescriptionBlock - posY1OfDescriptionBlock),
                                    abs(posY1OfRowDescriptionBlock - posY2OfDescriptionBlock)])
                    if distanceBetweenTwoRows > distance:
                        distanceBetweenTwoRows = distance


        # Vertical Oriented Textblock
        elif orientation == 1 or orientation == 3:
            for lineDescriptionBlock in secondTextBlock.lines:
                for lineRowDescriptionBlock in firstTextBlock.lines:
                    posX1OfDescriptionBlock = lineDescriptionBlock.posX1
                    posX2OfDescriptionBlock = lineDescriptionBlock.posX2
                    posX1OfRowDescriptionBlock = lineRowDescriptionBlock.posX1
                    posX2OfRowDescriptionBlock = lineRowDescriptionBlock.posX2
                    distance = min([abs(posX2OfRowDescriptionBlock - posX1OfDescriptionBlock),
                                    abs(posX1OfRowDescriptionBlock - posX2OfDescriptionBlock)])

                    if distanceBetweenTwoRows > distance:
                        distanceBetweenTwoRows = distance

        return int(distanceBetweenTwoRows)

    def check_preliminary_rows(self, predictionModel, path):

        self.check_modelbased_table(predictionModel, path)

        self.check_rulebased_table()

    def check_is_table(self):
        numberOfPermittedSentences = len(self.textBlocksOfTable) / 5 + 1
        if self.averageNumberOfElementsInRow() < 2:
            return False
        elif numberOfPermittedSentences < self.numberOfSentencesInTable():
            return False
        else:
            return True

    def extract_page(self, path_to_pdf: str):
        path_to_image = f"table/{self.pageNum}_{self.posX1}_{self.posY1}_{self.posX2}_{self.posY2}.png"

        doc = fitz.open(path_to_pdf)
        page = doc.load_page(self.pageNum)
        pix = page.get_pixmap()
        pix.writePNG(path_to_image)
        self.path_to_image = path_to_image

    def extract_image(self, path_to_pdf):
        path_to_image = f"table/{self.pageNum}_{self.posX1}_{self.posY1}_{self.posX2}_{self.posY2}.png"
        doc = fitz.open(path_to_pdf)
        page = doc.load_page(self.pageNum)
        clip = fitz.Rect(self.posX1, self.posY1, self.posX2, self.posY2)
        pix = page.get_pixmap(clip=clip)

        pix.writePNG(path_to_image)
        self.path_to_image = path_to_image

    def extract_as_image(self, path_to_pdf: str):

        path_to_image = f"table/{self.pageNum}_{self.posX1}_{self.posY1}_{self.posX2}_{self.posY2}.png"
        orientation = self.rows[0].orientation
        resize_factor = 1
        doc = fitz.open(path_to_pdf)
        page = doc.load_page(self.pageNum)
        mat = fitz.Matrix(resize_factor, resize_factor)  # zoom factor 4 in each direction
        clip = fitz.Rect((self.posX1, self.posY1), (self.posX2, self.posY2))  # the area we want
        pix = page.get_pixmap(matrix=mat, clip=clip)

        pix.writePNG(path_to_image)
        # pixels =
        self.path_to_image = path_to_image
        # rotate Image if necessary
        img = Image.open(path_to_image)
        img_size = img.size
        if orientation == 1:
            img = img.transpose(Image.ROTATE_270)
            img.save(path_to_image, 'PNG')
            img_size = img.size

        # Add a a white window in the background
        pil_background = Image.new(mode='RGB', size=(img_size[0] + 200, img_size[1] + 200), color=(255, 255, 255))
        pil_background.paste(img, (100, 100))
        pil_background.save(path_to_image, "PNG")

    def set_boundary(self, model, path):
        prediction_res = table_detection.predict_table_boundaries(model, self.path_to_image)
        res = table_detection.in_json(prediction_res, self.path_to_image)

        for prediction in res['predictions']:
            self.posX1 = int(prediction['x1'])
            self.posX2 = int(prediction['x2'])
            self.posY1 = int(prediction['y1'])
            self.posY2 = int(prediction['y2'])

            self.extract_image(path)

        pass

    def check_modelbased_table(self, model, path):

        prediction_res = table_detection.predict_table_boundaries(model, self.path_to_image)
        res = table_detection.in_json(prediction_res, self.path_to_image)

        for prediction in res['predictions']:
            self.posX1 = int(prediction['x1'])
            self.posX2 = int(prediction['x2'])
            self.posY1 = int(prediction['y1'])
            self.posY2 = int(prediction['y2'])
            self.extract_as_image(path)

        if len(res['predictions']) == 0:
            self.isTable = False
        else:
            for row in self.rows:
                if not row.is_in_prediction(res, self):
                    row.is_row = False

    def check_rulebased_table(self):
        '''
        Heuristic Rules from analysing different tables in papers

        :return:
        '''

        # consider only those, that contain more as one cell
        relevant_rows = [row for row in self.rows if len(row.cells) > 1]

        if len(relevant_rows) > 0:
            average_number_of_cells = sum([len(row.cells) for row in relevant_rows]) / len(relevant_rows)
        else:
            average_number_of_cells = 0
        for row in self.rows:
            text = " ".join([cell.text for cell in row.cells])
            # if the row is a sentence it is not a row
            if is_grammatically_sentence(text):
                row.is_row = False
            # if a row has just one cell it is not a row
            if len(row.cells) <= 1:
                row.is_row = False
            # if the row has significant different cells as every other row it is not a row
            if len(row.cells) < 0.5 * average_number_of_cells or 2 * average_number_of_cells <= len(row.cells):
                row.is_row = False

        # If a row that was identified as not a row is between two rows it is a row
        for num, row in enumerate(self.rows):
            if num > 0 and len(self.rows) < num - 1:
                if not row.is_row and self.rows[num - 1].is_row and self.rows[num + 1].is_row:
                    row.is_row = True

    def get_coexisiting_tables(self, tables):
        res = []
        for table in tables:
            if table.pageNum == self.pageNum:
                res.append(table)
        return res

    def reorganize_page(self, tables):
        tables.append(self)
        for table in tables:
            pass

    def get_preliminary_rows_of_table(self):
        textBlocks = self.getTextBlocksOfTable()

        for tBlock in textBlocks:
            tBlock.isPartOfTable = True

        self.textBlocksOfTable = textBlocks

        rowNumber = 1
        # Arrange the textBlocks in lines
        lines = {}
        for textBlock in textBlocks:
            for line in textBlock.lines:
                if textBlock.orientation == 0 or textBlock.orientation == 2:
                    lineMiddle = str(int((line.posY2 - line.posY1) / 2 + line.posY1))
                    if lineMiddle not in lines:
                        lines[lineMiddle] = [line]
                    else:
                        lines[lineMiddle].append(line)
                else:
                    lineMiddle = str(int((line.posX2 - line.posX1) / 2 + line.posX1))
                    if lineMiddle not in lines:
                        lines[lineMiddle] = [line]
                    else:
                        lines[lineMiddle].append(line)

        rows = [(rowPosition, spans) for rowPosition, spans in lines.items()]
        rows.sort(key=lambda x: x[0], reverse=False)

        for rowPosition, rowInformation in enumerate(rows):
            row = Row(rowPosition, rowInformation[1], self.descriptionBlock.orientation, self)
            self.rows.append(row)

        # Update coordinates of Table
        table_blocks = [self.descriptionBlock]
        table_blocks.extend(self.rows)
        self.posX1 = min([block.posX1 for block in table_blocks])
        self.posY1 = min([block.posY1 for block in table_blocks])
        self.posX2 = max([block.posX2 for block in table_blocks])
        self.posY2 = max([block.posY2 for block in table_blocks])

    def setTableInformations(self):
        # Build a grid, so that every row and column has the same number of elements
        # as the other columns and rows
        self._set_matrix()

        self._set_columns()
        # self.setColumns()

        # Identify the header of the table
        self.setHeader()

        # Order the rows and cells in the right order
        self.rearangeRows()
        self.rearangeCells()

    def rearangeCells(self):
        for row in self.rows:
            if row.orientation == 0:
                row.cells.sort(key=lambda x: x.posX1)
            elif row.orientation == 1:
                row.cells.sort(key=lambda x: x.posY1, reverse=True)

    #   self.setLabelAndDataCells()

    def _getPositionOfTable(self, tBlock1, tBlock2) -> (int, int, int, int):

        """
        Calculates the Coordinates of a Box containing two Boxes
        Needed. e.g. For Tables to merge to parts of a Table
        Args:
            tup1 (tuple): Position Tuple of Block One
            tup2 (tuple): Position Tuple of Block Two

        Returns:
            tuple: Position Tuple of the new Block
        """

        x1 = tBlock1.posX1 if tBlock1.posX1 <= tBlock2.posX1 else tBlock2.posX1
        y1 = tBlock1.posY1 if tBlock1.posY1 <= tBlock2.posY1 else tBlock2.posY1
        x2 = tBlock1.posX2 if tBlock1.posX2 > tBlock2.posX2 else tBlock2.posX2
        y2 = tBlock1.posY2 if tBlock1.posY2 > tBlock2.posY2 else tBlock2.posY2
        return (x1, y1, x2, y2)

    def getTextBlocksOfTable(self):
        firstTextBlock, distance = self.getRowTextBlockOfTable()
        orientation: int = self.getOrientation(firstTextBlock)
        spaceBetweenTwoLines: int = self.getSpaceBetweenTwoLines(orientation, self.descriptionBlock, firstTextBlock)
        positionOfTable: (int, int, int, int) = self._getPositionOfTable(self.descriptionBlock, firstTextBlock)
        textBlocksOfTable = [self.descriptionBlock, firstTextBlock]
        hasNextTextBlock = True

        while (hasNextTextBlock):
            previousTextBlock = firstTextBlock

            hasNextTextBlock = False
            for textBlock in self.textBlocks:
                if textBlock not in textBlocksOfTable:

                    if textBlock.orientation == orientation and textBlock.pageNum == previousTextBlock.pageNum:
                        if 2.5 * (spaceBetweenTwoLines + self.descriptionBlock.NORMAL_DISTANCE_BETWEEN_TWO_LINES) >= \
                                self.getSpaceBetweenTwoLines(
                                    orientation, previousTextBlock, textBlock):

                            if self.textBlocksAreOriented(textBlock, positionOfTable, orientation):
                                textBlocksOfTable.append(textBlock)
                                hasNextTextBlock = True
                                # Update Parameters
                                positionOfTable = self._getPositionOfTable(self.descriptionBlock, textBlock)
                                previousTextBlock = textBlock
        return textBlocksOfTable

    def textBlocksAreOriented(self, textBlock, tablePosition, orientation):
        # Ist es sinnvoll hier mit Prozenten zu rechnen?
        # Also bei displacement
        if orientation == 0 or orientation == 2:

            # verticalDisplacementAbove = textBlock.posY1 / tablePosition[1]
            # verticalDisplacementBelow = textBlock.posY2 / tablePosition[3]
            horizontalDisplacementToTheLeft = textBlock.posX1 / tablePosition[0]
            horizontalDisplacementCentral = ((textBlock.posX2 - textBlock.posX1) / 2 + textBlock.posX1) / \
                                            ((tablePosition[2] - tablePosition[0]) / 2 + tablePosition[0])

            # if 0.95 < verticalDisplacementAbove < 1.05 or 0.95 < verticalDisplacementBelow < 1.05:
            if 0.95 < horizontalDisplacementToTheLeft < 1.05 or 0.75 < \
                    horizontalDisplacementCentral < 1.25:
                return True

        else:
            # verticalDisplacementAbove = textBlock.posX1 / tablePosition[0]
            # verticalDisplacementBelow = textBlock.posX2 / tablePosition[2]
            horizontalDisplacementToTheLeft = textBlock.posY2 / tablePosition[3]
            horizontalDisplacementCentral = ((textBlock.posY2 - textBlock.posY1) / 2 + textBlock.posY1) / \
                                            ((tablePosition[3] - tablePosition[1]) / 2 + tablePosition[1])

            # if 0.95 < verticalDisplacementAbove < 1.05 or 0.95 < verticalDisplacementBelow < 1.05:
            if 0.95 < horizontalDisplacementToTheLeft < 1.05 or 0.75 < \
                    horizontalDisplacementCentral < 1.25:
                return True
        return False

    def getRowTextBlockOfTable(self):
        smallestDistance = 99999

        shortestNeighbour = None

        for row in self.potentialBlocksForTable:
            if row.pageNum == self.descriptionBlock.pageNum:
                if not row.isRecurringElement:
                    # Calculate the shortest Distance between two Blocks
                    smallestDistanceToBlock = self.distanceBetweenTwoLines(row, self.descriptionBlock)
                    if smallestDistance > smallestDistanceToBlock:
                        smallestDistance = smallestDistanceToBlock
                        shortestNeighbour = row

        return shortestNeighbour, smallestDistanceToBlock

    def distanceBetweenTwoPoints(self, textBlock_posX1, row_posY1, table_posX1, table_posY1):
        return ((textBlock_posX1 - table_posX1) ** 2 + (row_posY1 - table_posY1) ** 2) ** (1 / 2)

    def distanceBetweenTwoLines(self, tBlock1, tBlock2):
        orientation = tBlock1.orientation
        distance = 99999
        if orientation == 0 or orientation == 2:
            distance = min(abs(tBlock1.posY2 - tBlock2.posY1), abs(tBlock1.posY1 - tBlock2.posY2))
        else:
            distance = min(abs(tBlock1.posX2 - tBlock2.posX1), abs(tBlock1.posX1 - tBlock2.posX2))
        return distance

    def rearangeRows(self):
        if self.rows[0].orientation == 0 or self.rows[0].orientation == 2:
            self.rows.sort(key=lambda x: x.posY1, reverse=False)
        elif self.rows[0].orientation == 1 or self.rows[0].orientation == 3:
            self.rows.sort(key=lambda x: x.posX1, reverse=False)


class Row:
    IDCounter = 0

    def __init__(self, rowNumber: int, line, table: Table):
        self.rowNumber = rowNumber
        self.table: Table = table
        self.isHeader: bool = False
        self.posX1 = line.posX1 if line is not None else 0
        self.posY1 = line.posY1 if line is not None else 0
        self.posX2 = line.posX2 if line is not None else 0
        self.posY2 = line.posY2 if line is not None else 0
        self.line: Line = line
        self.id: int = Row.IDCounter
        self.is_row: bool = True
        self.orientation = 0
        self.is_table_header: bool = False
        self.cells: List[Cell] = []
        self.numberOfCols: int = 0

        Row.IDCounter += 1

    def get_number_of_words(self) -> int:
        return [_.mostCommonTypeOfWord for _ in self.cells].count("WORD")


    def to_io(self) -> io.Row:
        ''' Creates a Row for the responds model '''
        return io.Row(**{
                        "cells": [_.to_io() for _ in self.cells],
                        "type": "row"
                        })

    @classmethod
    def from_line(cls, line: Line, number, table):
        row = Row(number, line, table)
        return row

    def set_cells(self) -> None:
        cells = []
        spans = []
        for line in self.line.linesInDict:
            spans.extend(line['spans'])
        spans = self.identify_spans(spans)

        for span in spans:
            cell = Cell(span['bbox'], span['text'])
            cells.append(cell)

        self.cells = cells
        self.numberOfCols = len(self.cells)

    def save_headerline_as_str(self):
        self.rearangeCells()
        return self.getRowAsString()

    def is_in_prediction(self, predictions, table):
        # Image was vertical rotated
        if self.orientation == 1:
            rel_x1 = abs(table.posX1 - self.posX1)
            rel_x2 = rel_x1 + abs(self.posX1 - self.posX2)
            for prediction in predictions['predictions']:
                if int(prediction['y1']) <= rel_x1 <= int(prediction['y2']) or int(prediction['y1']) <= rel_x2 <= int(
                        prediction['y2']):
                    return True
        elif self.orientation == 0:
            rel_y1 = abs(table.posY1 - self.posY1)
            rel_y2 = rel_y1 + abs(self.posY1 - self.posY2)
            for prediction in predictions['predictions']:
                if int(prediction['y1']) <= rel_y1 <= int(prediction['y2']) or int(prediction['y1']) <= rel_y2 <= int(
                        prediction['y2']):
                    return True
        return False

    def saveAsDict(self, row_size):

        cells = [_.saveAsDict() for _ in self.cells]
        while len(cells) < row_size:
            cells.append({"text": " "})
        res = {
            "id": self.id,
            "cells": cells
        }
        return res

    def getPositionOfRow(self):
        position = [9999, 9999, -9999, -9999]
        for row in self.rowInformation:
            if row.posX1 < position[0]: position[0] = row.posX1
            if row.posY1 < position[1]: position[1] = row.posY1
            if row.posX2 > position[2]: position[2] = row.posX2
            if row.posY2 > position[3]: position[3] = row.posY2
        return position

    def merge_spans(self, span_1, span_2, orientation):
        bbox = (
            min(span_1['bbox'][0], span_2['bbox'][0]),
            min(span_1['bbox'][1], span_2['bbox'][1]),
            max(span_1['bbox'][2], span_2['bbox'][2]),
            max(span_1['bbox'][3], span_2['bbox'][3]),
        )
        if orientation == 1:
            if span_1['bbox'][1] > span_2['bbox'][1]:
                text = span_1['text'] + span_2['text']
            else:
                text = span_2['text'] + span_1['text']

        elif orientation == 0:
            if span_1['bbox'][0] < span_2['bbox'][0]:
                text = span_1['text'] + span_2['text']
            else:
                text = span_2['text'] + span_1['text']
        return {
            'bbox': bbox,
            'text': text
        }

    def getCells(self):
        elements = []
        for line in self.rowInformation:

            spans = line.getSpans(self.orientation)
            res = self.identify_spans(spans)

            for span in res:
                element = Cell(span['bbox'], span['text'])
                elements.append(element)
        return elements

    def identify_spans(self, spans):
        res = [spans[0]]
        for span_1 in spans[1:]:
            is_in_span = False
            for span_2 in res:
                if self.get_distance_between_two_spans(span_1, span_2,
                                                       self.orientation) <= self.table.descriptionBlock.NORMAL_WIDTH_OF_A_SPACE * 1.25:
                    res.remove(span_2)
                    span_2 = self.merge_spans(span_1, span_2, self.orientation)
                    res.append(span_2)
                    is_in_span = True
            if not is_in_span:
                res.append(span_1)
        return res

    def get_distance_between_two_spans(self, span_1, span_2, orientation):
        if orientation == 1:
            return min(abs(span_1['bbox'][1] - span_2['bbox'][3]), abs(span_1['bbox'][3] - span_2['bbox'][1]))
        else:
            return min(abs(span_1['bbox'][0] - span_2['bbox'][2]), abs(span_1['bbox'][2] - span_2['bbox'][0]))

    def rearangeCells(self):
        if self.orientation == 0 or self.orientation == 2:
            self.cells.sort(key=lambda x: x.posX1, reverse=False)
        elif self.orientation == 1 or self.orientation == 3:
            self.cells.sort(key=lambda x: x.posY1, reverse=True)

    def getRowAsString(self):
        res = ""
        for element in self.cells:
            res += element.text + " "
        return res


class Column:
    IDCounter = 0

    def __init__(self, row_number, posX1, posX2, posY1, posY2, table: Table):
        self.rowNumber = row_number
        self.table: Table = table
        self.isHeader: bool = False
        self.posX1 = posX1
        self.posY1 = posY1
        self.posX2 = posX2
        self.posY2 = posY2
        self.id: int = Column.IDCounter
        self.is_row: bool = True
        self.orientation = 0
        self.is_table_header = False
        self.cells: List[Cell] = []
        self.numberOfCols: int = 0

        Column.IDCounter += 1

    def to_io(self) -> io.Column:
        ''' Creates a Row for the responds model '''
        return io.Column(**{
                            "cells": [_.to_io() for _ in self.cells],
                            "type": "row"
                        })

    def get_number_of_words(self) -> int:
        return [_.mostCommonTypeOfWord for _ in self.cells].count("WORD")


class Cell:
    IDCounter = 0

    def __init__(self, coordinates, text, column=None, row=None):
        self.posX1 = int(coordinates[0])
        self.posY1 = int(coordinates[1])
        self.posX2 = int(coordinates[2])
        self.posY2 = int(coordinates[3])
        self.centerX = int((self.posX2 - self.posX1) / 2 + self.posX1)
        self.centerY = int((self.posY2 - self.posY1) / 2 + self.posY1)
        self.text = text
        self.id: int = Cell.IDCounter
        self.numberOfWords: int = 0
        self.mostCommonTypeOfWord: str = ""
        self._setNumberAndTypeOfWordsInCell()
        self.isLabel = False
        self.column = column
        self.row = row
        self.not_activated = True
        Cell.IDCounter += 1

    def to_io(self) -> io.Cell:
        ''' Creates a Cell for the responds model'''
        return io.Cell(**{
            "text": self.text,
            "category": self.mostCommonTypeOfWord,
            "type": self.mostCommonTypeOfWord
        })

    def _setNumberAndTypeOfWordsInCell(self):
        numberOfWords, typesOfWord = get_type_frequency(self.text)

        self.mostCommonTypeOfWord = typesOfWord[0][0]
        self.numberOfWords = numberOfWords



    def saveAsDict(self):
        res = {
            "id": self.id,
            "text": self.text
        }
        return res
