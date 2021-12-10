from io import BytesIO
import os
from datetime import datetime

import aiofiles as aiofiles
import requests
import config
import sys
import base64
import json

counter = 0


def save_data_as_json(data, path):
    with open(path, "w") as file:
        file.write(json.dumps(data, indent=4))


