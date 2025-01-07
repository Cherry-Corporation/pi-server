from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Path to the file you want to serve
FILE_PATH = "/home/pi/pi-server/vms/vm-1/alpine.qcow2"  # Change this to the correct path of the file on your Pi

# Endpoint to serve the file
@app.get("/download")
async def download_file():
    if not os.path.exists(FILE_PATH):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(FILE_PATH, media_type='application/octet-stream', filename="alpine.qcow2")
