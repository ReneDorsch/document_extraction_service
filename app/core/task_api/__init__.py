from __future__ import annotations
import os
from typing import Any

from pydantic import BaseModel, Field

from datetime import datetime
import aiofiles
from ..config import INPUT_DIRECTORY
from ..extraction_modul.apis import TextStrategy, TableStrategy, MetadataStrategy, ImageStrategy
from ..extraction_modul.extraction_model import PDF_Extraction


textAPI: TextStrategy = TextStrategy()
tableAPI: TableStrategy = TableStrategy()
metadataAPI: MetadataStrategy = MetadataStrategy()
imageAPI: ImageStrategy = ImageStrategy()


class Task:
    """ A Class representing disitinct tasks as e.g. defined by execute_pdf_extraction.
    If you want to add additional Tasks describe the single functions of them in a staticmethod.

    This Task has to have a few concepts integrated:
    - It has to change the status to finished if the task is done.
    - And it has to save the transformed data in the TaskSettings.

    A Template for this would be:

    @staticmethod
    def do_some_task(task_settings: TaskSettings) -> None:
        # Do your stuff here
        ...
        task_settings.data = transforemd_data
        task_settings.status = 'finished'
    """
    @staticmethod
    def execute_pdf_extraction(task_settings: TaskSettings) -> None:
        """ Extracts Text, Tables, Images, and Metadata from the PDF. """
        data = PDF_Extraction.read_pdf(path_to_pdf=task_settings.path_to_input_file)

        textAPI.preprocess_data(data)
        tableAPI.preprocess_data(data)
        imageAPI.preprocess_data(data)
        metadataAPI.preprocess_data(data)


        tableAPI.process_data(data)
        metadataAPI.process_data(data)
        imageAPI.process_data(data)
        textAPI.process_data(data)

        tableAPI.postprocess_data(data)
        textAPI.postprocess_data(data)


        task_settings.data = data
        task_settings.status = 'finished'

async def asy_save_pdf(pdf: str):
    """ Util function to save a file. """
    now = datetime.now()
    date_and_time: str = now.strftime('%m_%d_%Y_%H_%M_%S_%f')
    path_to_pdf = os.path.join(INPUT_DIRECTORY, f'./{date_and_time}.pdf')

    async with aiofiles.open(path_to_pdf, 'wb') as pdf_doc:
        content = await pdf.read()
        await pdf_doc.write(content)

    return path_to_pdf

def save_pdf(pdf: str):
    """ Util function to save a file. """
    now = datetime.now()
    date_and_time: str = now.strftime('%m_%d_%Y_%H_%M_%S_%f')
    path_to_pdf = os.path.join(INPUT_DIRECTORY, f'./{date_and_time}.pdf')

    with open(path_to_pdf, 'wb') as pdf_doc:
        pdf_doc.write(pdf)

    return path_to_pdf


class TaskSettings(BaseModel):
    """ A class that defines settings for a task that has to be executed. """
    client: str = Field(description="The IP of the client. ")
    document_id: str = Field(description="A unique identifier to a document. ")
    path_to_input_file: str = Field(default='',
                                    description="The path to the input file.")
    path_to_output_file: str = Field(default="",
                                     description="The path to the output file. ")
    status: str = 'working'
    data: Any = Field(default=None)


    @classmethod
    async def asy_create(cls, **data):
        """ Creates a new Task asynchronicity. """
        self = cls(**data)
        pdf_file = data['file']
        pdf_path = await asy_save_pdf(pdf_file)
        log_path = pdf_path.replace('input', 'output').replace('pdf', 'json')
        self.path_to_input_file = pdf_path
        self.path_to_output_file = log_path
        return self

    @classmethod
    def create(cls, **data):
        """ Creates a new Task. """
        self = cls(**data)
        pdf_file = data['file']
        pdf_path = save_pdf(pdf_file)
        log_path = pdf_path.replace('input', 'output').replace('pdf', 'json')
        self.path_to_input_file = pdf_path
        self.path_to_output_file = log_path
        return self

    def finish_task(self) -> None:
        """ Cleaning up. """
        # Delete input and output files.
        os.remove(self.path_to_input_file)
        os.remove(self.path_to_output_file)
        del self


class TaskBuilder:
    """ A Builder Class to create Tasksettings. """

    # Add here additional Tasks
    tasks = {'pdf_to_data': Task.execute_pdf_extraction}

    def __init__(self):
        self.tasks = {}

    async def asy_create_task(self, task: str, **args) -> TaskSettings:
        """ Creates a new Task asynchronicity. """
        executable_task = TaskBuilder.tasks[task]
        task_settings: TaskSettings = await TaskSettings.asy_create(**args)
        self.tasks[task_settings.document_id] = {'task': executable_task}
        return task_settings

    def create_task(self, task, **args) -> TaskSettings:
        """ Creates a new Task. """
        task = TaskBuilder.tasks[task]
        task_settings = TaskSettings.create(**args)
        self.tasks[task_settings.document_id] = task
        return task_settings

    def perform_task(self, task_settings) -> None:
        """ Executes the task as defined in the TaskSettings. """
        executable = self.tasks[task_settings.document_id]
        executable(task_settings)


class TaskStatus(BaseModel):
    """ An Model that defines the dataformat for the output. """
    status: str = Field(description="The Status of the task. This can be either 'working' or 'finished'. "
                                    "If the status is 'working' the results of the task are not ready for the response."
                                    "If the status is 'finished' call the api /extraction/get_data/{document_id}.")
    document_id: str = Field(description="An id specified by the user to distinguish the extraction tasks. ")

