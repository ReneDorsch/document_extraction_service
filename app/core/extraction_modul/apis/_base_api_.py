from abc import ABC, abstractmethod

from ..extraction_model import PDF_Extraction



class TransformationStrategy(ABC):

    @abstractmethod
    def preprocess_data(self, data: PDF_Extraction) -> None:
        ''' Abstract method to preprocess the data in some kind. '''

    @abstractmethod
    def process_data(self, data: PDF_Extraction) -> None:
        ''' Abstract method to process the data in some kind. '''

    @abstractmethod
    def postprocess_data(self, data: PDF_Extraction) -> None:
        ''' Abstract method to refine the data in some kind. '''