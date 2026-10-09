"""Persistent, sequential Yandex video import queue backed by module rows."""
import json
import logging
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, unquote, urlencode

from ..db import SessionLocal
from ..models import Module
from ..config import settings

logger = logging.getLogger(__name__)

def is_yandex(url):
    return urlsplit(url).hostname == 'disk.yandex.ru' and urlsplit(url).path.startswith('/d/')

def run():
    while True:
        try:
            process_next()
        except Exception:
            logger.exception('Video import worker failed')
        time.sleep(5)

def process_next():
    with SessionLocal() as db:
        module = db.query(Module).filter(Module.video_import_status.in_(['queued', 'downloading', 'converting'])).order_by(Module.id).first()
        if not module:
            return
        module_id, source_url = module.id, module.video_url
        directory = Path(settings.media_root) / 'education/videos'
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / f'import_{module_id}.source'
        output = directory / f'{uuid.uuid4().hex}.mp4'
        try:
            module.video_import_status = 'downloading'
            db.commit()
            parts = urlsplit(source_url).path.split('/')[2:]
            params = {'public_key': f'https://disk.yandex.ru/d/{parts[0]}', 'path': '/' + unquote('/'.join(parts[1:]))}
            api = 'https://cloud-api.yandex.net/v1/disk/public/resources/download?' + urlencode(params)
            result = subprocess.check_output(['curl', '-fsSL', '--retry', '3', '--max-time', '60', api])
            href = json.loads(result)['href']
            subprocess.run(['curl', '-fL', '--retry', '3', '-o', str(source), href], check=True)
            module.video_import_status = 'converting'
            db.commit()
            subprocess.run([
                'ffmpeg', '-nostdin', '-y', '-i', str(source),
                '-map', '0:v:0', '-map', '0:a:0?',
                # 1080p is enough for the LMS and keeps peak RAM usage safe on the server.
                '-vf', r'scale=w=min(1920\,iw):h=-2',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-preset', 'veryfast', '-threads', '2', '-crf', '23',
                '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(output)
            ], check=True)
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(output), '-f', 'null', '-'], check=True)
            db.refresh(module)
            if module.video_url != source_url or module.video_import_status != 'converting':
                output.unlink(missing_ok=True)
                return
            module.private_video = str(output.relative_to(settings.media_root))
            module.video_import_status = 'ready'
            db.commit()
            source.unlink(missing_ok=True)
        except Exception:
            db.rollback()
            logger.exception('Video import failed for module %s', module_id)
            output.unlink(missing_ok=True)
            db.refresh(module)
            if module.video_url == source_url:
                module.video_import_status = 'failed'
                db.commit()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()
