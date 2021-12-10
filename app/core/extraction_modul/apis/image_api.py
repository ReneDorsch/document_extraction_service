from ._base_api_ import TransformationStrategy
from ..extraction_model import PDF_Extraction
from app.core.config import IMAGE_DIRECTORY
from ..datamodels.image_models import Image
from ..datamodels.internal_models import TextBlock
from typing import List
class ImageStrategy(TransformationStrategy):
    ''' An Agent performing all necessary tasks for the extraction and transformation of the image_file. '''

    def __init__(self):
        super().__init__()

    def postprocess_data(self, data: PDF_Extraction) -> None:
        pass

    def preprocess_data(self, data: PDF_Extraction) -> None:
        image_descriptions = self.identify_image_descriptions(data)

        for imageBlock in image_descriptions:
            image = Image(imageBlock)
            data.images.append(image)

        self.identify_surrounding_text_blocks(data)
        self.identify_coordinates_for_images(data)
        images = self.check_images(data)
        data.images = images

    def process_data(self, data: PDF_Extraction) -> None:
        ''' Processes the found images. '''
        for image in data.images:
            if image.is_image:
                image.get_image_of_image(data.pages)
            else:
                for tBlock in image.textBlocksOfImage:
                    tBlock.isPartOfImage = False

    def check_images(self, data: PDF_Extraction) -> List[Image]:
        '''
        Checks after preProcessing if a previous found image_file is indeed an image_file
        :return:
        '''
        res = []
        for image in data.images:
            image.checkIsImage()
            if image.is_image:
                res.append(image)
        return res

    def identify_coordinates_for_images(self, data: PDF_Extraction)-> None:
        for image in data.images:
            image.setCoordinatesOfPicture()

    def identify_surrounding_text_blocks(self, data: PDF_Extraction) -> None:
        '''
        Identifies Textblocks which are around the Descriptions of images
        :return:
        '''

        def is_centered(textBlock, other_textBlocks):
            textBlocks = [_ for _ in other_textBlocks if _.isPartOfText]
            centers = [_.posX1 + (_.posX2 - _.posX1) / 2 for _ in textBlocks]
            center_tBlock = textBlock.posX1 + (textBlock.posX2 - textBlock.posX1) / 2
            for center in centers:
                if center * 0.9 <= center_tBlock <= center * 1.1:
                    return False
            return True


        for image in data.images:
            textBlocks = [_ for _ in data.textBlocks if _.pageNum == image.pageNum]
            textBlock = None

            for tBlock in textBlocks:
                if image.descriptionText == tBlock.text:
                    textBlock = tBlock

            textBlocks.remove(textBlock)

            is_in_center: bool = is_centered(textBlock, data.textBlocks)

            if is_in_center:
                image.set_upper_and_lower(textBlock, textBlocks)
            else:
                image.setSurroundingTextBlocks(textBlock, textBlocks)



    def identify_image_descriptions(self, data: PDF_Extraction) -> List[TextBlock]:
        '''
        Identifies Descriptions of the Images
        :return:
        '''
        res = []
        for textBlock in data.textBlocks:
            text = textBlock.text.lstrip().lower()
            if text.startswith("fig.") or text.startswith("figure"):
                # If the textBlock contains  more as 1000 Chars it is
                # probably not be an image_file description
                if len(text) < 1000:
                    res.append(textBlock)
        return res

    def _set_images(self) -> 'Image':
        print("Create Images")

    def _extract_images(self, data: PDF_Extraction) -> None:
        ''' Get the tables as images and saves them'''
        for image in data.grobid_results['images']:
            image.process_image(data.pages)


    def _delete_images_from_text(self, data: PDF_Extraction) -> None:
        ''' Deletes the tables form the text part. '''
        images = data.grobid_results['images']
        chapters = data.grobid_results['text']['chapters']

        # Deltes sentences from the images.
        for chapter in chapters:
            for image in images:
                for paragraph in chapter.paragraphs:
                    for chapter_sentence in paragraph.sentences:
                        if image.image_description.text == chapter_sentence.text:
                            paragraph.remove_sentence(chapter_sentence)

        # Deletes empty paragraphs
        for chapter in chapters:
            for paragraph in chapter.paragraphs:
                if len(paragraph.sentences) == 0:
                    chapter.remove_paragraph(paragraph)

        # Deletes empty chapters
        removable_chapters = [_ for _ in chapters if len(_.paragraphs) == 0]
        data.grobid_results['text']['chapters'] = [chapter for chapter in chapters if chapter not in removable_chapters]



