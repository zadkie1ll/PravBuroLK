"""Persistent, sequential uploaded/Yandex video queue backed by module rows."""
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
        uploaded_source = module.video_import_source
        directory = Path(settings.media_root) / 'education/videos'
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / f'import_{module_id}.source'
        output = directory / f'{uuid.uuid4().hex}.mp4'
        def current_job():
            return db.query(Module).filter(
                Module.id == module_id, Module.video_url == source_url,
                Module.video_import_source == uploaded_source,
                Module.video_import_status.in_(['queued', 'downloading', 'converting']),
            )
        try:
            if uploaded_source:
                source = (Path(settings.media_root) / uploaded_source).resolve()
                allowed = (Path(settings.media_root) / 'education/video_sources').resolve()
                if not source.is_relative_to(allowed) or not source.is_file():
                    raise ValueError('Uploaded source is unavailable')
            else:
                if not is_yandex(source_url):
                    raise ValueError('Unsupported video source')
                current_job().update({Module.video_import_status: 'downloading'}, synchronize_session=False)
                db.commit()
                parts = urlsplit(source_url).path.split('/')[2:]
                params = {'public_key': f'https://disk.yandex.ru/d/{parts[0]}', 'path': '/' + unquote('/'.join(parts[1:]))}
                api = 'https://cloud-api.yandex.net/v1/disk/public/resources/download?' + urlencode(params)
                result = subprocess.check_output(['curl', '-fsSL', '--retry', '3', '--max-time', '60', api])
                href = json.loads(result)['href']
                subprocess.run(['curl', '-fL', '--retry', '3', '-o', str(source), href], check=True)
            if not current_job().update({Module.video_import_status: 'converting'}, synchronize_session=False):
                db.rollback()
                return
            db.commit()
            logger.info('Converting video for module %s', module_id)
            subprocess.run([
                'ffmpeg', '-nostdin', '-y', '-i', str(source),
                '-map', '0:v:0', '-map', '0:a:0?',
                # 1080p is enough for the LMS and keeps peak RAM usage safe on the server.
                '-vf', r'scale=w=min(1920\,iw):h=-2',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-preset', 'veryfast', '-threads', '2', '-crf', '23',
                '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(output)
            ], check=True)
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-threads', '2', '-i', str(output), '-f', 'null', '-'], check=True)
            if not current_job().update({
                Module.private_video: str(output.relative_to(settings.media_root)),
                Module.video_import_status: 'ready', Module.video_import_source: '',
            }, synchronize_session=False):
                db.rollback()
                output.unlink(missing_ok=True)
                return
            db.commit()
            try:
                source.unlink(missing_ok=True)
            except OSError:
                # The ready output is already published: cleanup must not delete it.
                logger.warning('Could not remove video source for module %s', module_id)
            logger.info('Video ready for module %s', module_id)
        except Exception:
            db.rollback()
            logger.exception('Video import failed for module %s', module_id)
            output.unlink(missing_ok=True)
            current_job().update({Module.video_import_status: 'failed'}, synchronize_session=False)
            db.commit()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()
