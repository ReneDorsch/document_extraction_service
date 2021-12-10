from typing import List
import app.core.schemas.datamodels as io
class Reference:

    def __init__(self, doi, author_lastName, title):
        self.title = title
        self.doi = doi
        self.authors = [Author(firstname="NOT_AVAILABLE", lastname=author_lastName)]

    def to_io(self) -> io.Reference:
        return io.Reference(**{
            "doi": self.doi,
            "authors": [_.to_io() for _ in self.authors],
            "title": self.title
        })


class Author:
    def __init__(self, firstname, lastname):
        self.firstname: str = firstname
        self.lastname: str = lastname

    def to_io(self) -> io.Author:
        return io.Author(**{
            "first_name": self.firstname,
            "last_name": self.lastname
        })

class Metadata:

    def __init__(self):
        self.abstractAsString: str = ""
        self.doi = ""
        self.authors: List[str] = []
        self.references: List[Reference] = []
        self.publisher: str = ""
        self.title: str = ""
        self.subTitle: str = ""
        self.journal: str = ""
        self.metaDataFromCrossRef = ""
        self.ISSN: str = ""
        self.abstract: 'Chapter' = None

    def to_io(self) -> io.MetaData:

        ''' Creates a Row for the responds model '''
        return io.MetaData(**{
                              "abstract": self.abstract.to_io(),
                              "references": [_.to_io() for _ in self.references],
                              "title": self.title,
                              "subtitle": self.subTitle,
                              "authors": [_.to_io() for _ in self.authors],
                              "doi": self.doi
                              })


    def saveAsDict(self):
        res = {}
        if self.abstract is not None: res["abstract"] = self.abstract.save_as_dict()
        res["references"] = self.references
        res["issn"] = self.ISSN
        res["journal"] = self.journal
        res["title"] = self.title
        res["subtitle"] = self.subTitle
        res["publisher"] = self.publisher
        res["authors"] = self.authors
        res["doi"] = self.doi

        return res