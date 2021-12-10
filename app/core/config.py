import os

CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
TESTFILE = os.path.join(CURRENT_DIRECTORY, 'extraction_modul/testFiles/j.jmrt.2019.12.072.pdf')
INPUT_DIRECTORY = os.path.join(CURRENT_DIRECTORY, 'extraction_modul/logging/input/')
IMAGE_DIRECTORY = os.path.join(CURRENT_DIRECTORY, 'extraction_modul/logging/images/')
TMP_DIRECTORY = os.path.join(CURRENT_DIRECTORY, 'files/tmp')


METADATA_PATTERNS = os.path.join(CURRENT_DIRECTORY, 'files/meta_data_pattern.json')


TABLE_MODEL_GPU = os.path.join(CURRENT_DIRECTORY, 'detection_models/models/gpu_table_detection_model.pth')
TABLE_MODEL_CPU = os.path.join(CURRENT_DIRECTORY, 'detection_models/models/cpu_table_detection_model.pth')
TABLE_MODEL_CONFIG = os.path.join(CURRENT_DIRECTORY, 'detection_models/models/cascade_mask_rcnn_hrnetv2p_w32_20e_v2.py')

TABLE_MODEL_CATEGORIES = {
              0: 'Bordered_Table',
              1: 'Cell',
              2: 'Borderless_Table'
            }

