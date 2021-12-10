from app.core.config import METADATA_PATTERNS
from app.core.extraction_modul.datamodels.internal_models import TextBlock
from typing import List
import json
import re

def check_for_metadata(textBlocks: List[TextBlock]):
    for textBlock in textBlocks:
        if is_metadata(textBlock.text):
            textBlock.isPartOfText = False
    return textBlocks

def is_metadata(text) -> bool:
    with open(METADATA_PATTERNS, mode="rb") as read_file:
        metadataPatterns = json.load(read_file)
    for metaData, pattern in metadataPatterns.items():
        res = re.findall(pattern, text.lower())
        if res != [] :
            return True

    return False