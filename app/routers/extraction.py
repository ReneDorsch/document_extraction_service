import base64

from fastapi import APIRouter, File, UploadFile, BackgroundTasks, Request, Form, HTTPException, Response
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND, HTTP_200_OK

from app.core.schemas.datamodels import Document
from app.core.task_api import TaskBuilder, TaskStatus

from pydantic import BaseModel

router = APIRouter()

# The APIs necessary for the tasks

taskBuilderAPI: TaskBuilder = TaskBuilder()
finished_tasks_database = dict()


class Data(BaseModel):
    document_id: str
    file: str


def get_state(document_id: str):
    """ Gets the state of the document. If the document is ready for the response to the Requester the state finished
    will be called."""
    if document_id in finished_tasks_database:
        return 'finished'
    else:
        return 'working'


def get_results(document_id: str) -> Document:
    """ Returns the results of the document as the outputmodel (document). """
    return finished_tasks_database[document_id].data.to_output_model(document_id)


def get_results_images(document_id: str) -> Document:
    """ Returns the images of a result of the document as the outputmodel (document). """
    return finished_tasks_database[document_id].data.to_image_model(document_id)


def get_results_metadata(document_id: str) -> Document:
    """ Returns the metadata of a result of the document as the outputmodel (document). """
    return finished_tasks_database[document_id].data.to_metadata_model(document_id)


def get_results_text(document_id: str) -> Document:
    """ Returns the text of a result of the document as the outputmodel (document). """
    return finished_tasks_database[document_id].data.to_text_model(document_id)


def get_results_tables(document_id: str) -> Document:
    """ Returns the tables of a result of the document as the outputmodel (document). """
    return finished_tasks_database[document_id].data.to_table_model(document_id)


@router.get('/extraction/get_task_extraction/', response_model=Document, status_code=HTTP_200_OK)
def get_task_extraction(document_id: str):
    """ An API to get the extraction of the task. """
    state: str = get_state(document_id)
    if state == 'finished':
        res: Document = get_results(document_id)
        return res
    else:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="Document not ready or not found")


@router.get('/extraction/get_image_extraction/', response_model=Document, status_code=HTTP_200_OK)
def get_task_extraction(document_id: str):
    """ An API to get the extraction of the task. """
    state: str = get_state(document_id)
    if state == 'finished':
        res: Document = get_results_images(document_id)
        return res
    else:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="Document not ready or not found")


@router.get('/extraction/get_metadata_extraction/', response_model=Document, status_code=HTTP_200_OK)
def get_task_extraction(document_id: str):
    """ An API to get the extraction of the task. """
    state: str = get_state(document_id)
    if state == 'finished':
        res: Document = get_results_metadata(document_id)
        return res
    else:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="Document not ready or not found")


@router.get('/extraction/get_text_extraction/', response_model=Document, status_code=HTTP_200_OK)
def get_task_extraction(document_id: str):
    """ An API to get the extraction of the task. """
    state: str = get_state(document_id)
    if state == 'finished':
        res: Document = get_results_text(document_id)
        return res
    else:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="Document not ready or not found")


@router.get('/extraction/get_table_extraction/', response_model=Document, status_code=HTTP_200_OK)
def get_task_extraction(document_id: str):
    """ An API to get the extraction of the task. """
    state: str = get_state(document_id)
    if state == 'finished':
        res: Document = get_results_tables(document_id)
        return res
    else:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="Document not ready or not found")


@router.get('/extraction/has_extraction/')
def has_extraction(document_id: str, response: Response):
    """ An API to get the extraction of the task. """
    state = get_state(document_id)
    if state == 'finished':
        response.status_code = HTTP_201_CREATED
    else:
        response.status_code = HTTP_204_NO_CONTENT
    return {}



@router.get('/extraction/get_task_extraction/', response_model=Document, status_code=HTTP_200_OK)
def get_task_extraction(document_id: str):
    """ An API to get the extraction of the task. """
    state: str = get_state(document_id)
    if state == 'finished':
        res: Document = get_results(document_id)
        return res
    else:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="Document not ready or not found")


@router.post('/extraction/transform_pdf_to_data', response_model=TaskStatus, status_code=HTTP_201_CREATED)
def transform_pdf_to_text(request: Request,
                          background_tasks: BackgroundTasks,
                          data: Data
                          ):
    """ An API that extracts Information from a single PDF-Document. """

    _job = dict(
        status='pending',
        document_id=data.document_id
    )
    background_tasks.add_task(bg_transform_pdf_to_data, request, data.document_id, data.file)
    return _job


async def asy_bg_transform_pdf_to_data(request, document_id, file):
    task = await taskBuilderAPI.asy_create_task(task='pdf_to_data',
                                                client=request.client.host,
                                                document_id=document_id,
                                                file=file)

    taskBuilderAPI.perform_task(task)
    finished_tasks_database.update({
        document_id: task
    })


def bg_transform_pdf_to_data(request, document_id, file):
    file = base64.urlsafe_b64decode(file.encode('utf-8'))
    task = taskBuilderAPI.create_task(task='pdf_to_data',
                                      client=request.client.host,
                                      document_id=document_id,
                                      file=file)

    taskBuilderAPI.perform_task(task)
    finished_tasks_database.update({
        document_id: task
    })
