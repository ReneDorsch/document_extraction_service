import subprocess
from typing import List

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from routers import extraction

app = FastAPI()
app.include_router(extraction.router)

subprocesses: List[subprocess.Popen] = []


@app.on_event("startup")
async def startup_event():
    """ Start GrobID in the Background. """

    pass


@app.on_event("shutdown")
def shutdown_event():
    """ Stopp all subprocesses if this program stops. """
    for process in subprocesses:
        process.kill()


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    """ Redirects every wrong Request to the docs. """
    return RedirectResponse("/docs")


uvicorn.run(app, port=8002, host='0.0.0.0')
