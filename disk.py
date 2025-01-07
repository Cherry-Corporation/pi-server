from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os

app = FastAPI()


FILE_PATH = "/home/pi/pi-server/vms/vm-1/alpine.qcow2" 

# Endpoint to serve
@app.get("/download")
async def download_file():
    if not os.path.exists(FILE_PATH):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(FILE_PATH, media_type='application/octet-stream', filename="alpine.qcow2")
