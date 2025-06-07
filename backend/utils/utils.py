import base64
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import requests
from fastapi import HTTPException
from PIL import Image

from .. import __version__
from ..models import Settings

settings = Settings()

def generate_filename(format: str) -> str:
    return f"{uuid4()}.{format}"


def assets_folder_path() -> Path:
    return Path(settings.ASSETS_FOLDER)


def generate_api_token() -> str:
    return str(uuid4())


def b64_decode(data: str) -> bytes:
    return (
        base64.b64decode(data.split(",", 1)[1])
        if data.startswith("data:image/")
        else base64.b64decode(data)
    )


def remove_image(path: str):
    try:
        Path(assets_folder_path() / path).unlink()
    except FileNotFoundError:
        raise Exception("Image not found")
    except OSError as e:
        raise Exception("Error deleting image:", e)


def parse_str_or_date_to_date(cdate: str | date) -> date:
    if isinstance(cdate, str):
        try:
            return date.fromisoformat(cdate)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format, use YYYY-MM-DD"
            )
    return cdate


async def download_file(link: str) -> str:
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(link)
            response.raise_for_status()
            
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.write(response.content)
            temp_file.close()
            
            return temp_file.name
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Failed to download file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error during file download: {e}")


def check_update():
    url = "https://api.github.com/repos/itskovacs/wingfit/releases/latest"
    try:
        response = requests.get(url)
        response.raise_for_status()

        latest_version = response.json()["tag_name"]
        if __version__ != latest_version:
            return latest_version

        return None

    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Couldn't verify for update")


def save_image(content: bytes, path: Path, size: tuple[int, int] = (128, 128)) -> bool:
    try:
        with Image.open(BytesIO(content)) as im:
            if size[0]:  # If not 0, keep image ratio
                im_ratio = im.width / im.height
                target_ratio = size[0] / size[1]

                if im_ratio > target_ratio:
                    new_height = size[1]
                    new_width = int(new_height * im_ratio)
                else:
                    new_width = size[0]
                    new_height = int(new_width / im_ratio)

                im = im.resize((new_width, new_height), Image.LANCZOS)

                left = (im.width - size[0]) // 2
                top = (im.height - size[1]) // 2
                right = left + size[0]
                bottom = top + size[1]

                im = im.crop((left, top, right, bottom))

            im.save(path, format=im.format)
            return True
    except Exception:
        # TODO Enhance logging
        ...
    return False
