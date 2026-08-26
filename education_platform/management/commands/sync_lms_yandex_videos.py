import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from education_platform.models import Course


API_BASE = "https://cloud-api.yandex.net/v1/disk"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}

COURSE_ALIASES = {
    "введение": "Введение",
    "отдел продаж базовый модуль": "Продажи - базовый",
    "отдель продаж базовый модуль": "Продажи - базовый",
    "маркетинг базовый модуль": "Маркетинг - базовый",
    "модерация базовый модуль": "Модерация базовый",
    "первая линия базовый модуль": "Первая линия - базовый",
    "отдел сопровождения базовый модуль": "Сопровождение - базовый",
    "отдель продаж": "Продажи - продвинутый",
    "отдел продаж": "Продажи - продвинутый",
    "отдель продаж продвинутый модуль": "Продажи - продвинутый",
    "отдел продаж продвинутый модуль": "Продажи - продвинутый",
}


class YandexDiskClient:
    def __init__(self, token=None, public_key=None, timeout=60):
        self.token = token
        self.public_key = public_key
        self.timeout = timeout

    @property
    def headers(self):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"OAuth {self.token}"
        return headers

    def list_dir(self, path, limit=1000):
        if self.public_key:
            endpoint = f"{API_BASE}/public/resources"
            params = {"public_key": self.public_key, "limit": limit}
            if path and path != "/":
                params["path"] = path
        else:
            endpoint = f"{API_BASE}/resources"
            params = {"path": path or "/", "limit": limit}

        data = self._get_json(endpoint, params)
        if data.get("type") != "dir":
            raise CommandError(f"Yandex path is not a directory: {path}")
        return data.get("_embedded", {}).get("items", [])

    def get_download_url(self, path):
        if self.public_key:
            endpoint = f"{API_BASE}/public/resources/download"
            params = {"public_key": self.public_key, "path": path}
        else:
            endpoint = f"{API_BASE}/resources/download"
            params = {"path": path}
        data = self._get_json(endpoint, params)
        href = data.get("href")
        if not href:
            raise CommandError(f"Yandex did not return a download URL for {path}")
        return href

    def download(self, path, destination):
        href = self.get_download_url(path)
        with requests.get(href, stream=True, timeout=self.timeout) as response:
            response.raise_for_status()
            with open(destination, "wb") as target:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        target.write(chunk)

    def _get_json(self, endpoint, params):
        url = f"{endpoint}?{urlencode(params)}"
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        if response.status_code >= 400:
            raise CommandError(f"Yandex Disk API error {response.status_code}: {response.text[:300]}")
        return response.json()


class Command(BaseCommand):
    help = "Sync LMS module videos from Yandex Disk into private_media."

    def add_arguments(self, parser):
        parser.add_argument("--public-key", default=os.getenv("YANDEX_DISK_PUBLIC_KEY", ""))
        parser.add_argument("--token", default=os.getenv("YANDEX_DISK_TOKEN", ""))
        parser.add_argument("--root-path", default=os.getenv("YANDEX_DISK_LMS_ROOT", "/"))
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("--clear-video-url", action="store_true")
        parser.add_argument("--include-inactive", action="store_true")
        parser.add_argument("--skip-space-check", action="store_true")
        parser.add_argument(
            "--course",
            action="append",
            dest="courses",
            help="Limit sync to a course name. Can be passed multiple times.",
        )

    def handle(self, *args, **options):
        public_key = self._clean_public_key(options["public_key"])
        token = options["token"].strip()
        if not public_key and not token:
            raise CommandError("Provide --public-key or --token/YANDEX_DISK_TOKEN.")

        client = YandexDiskClient(token=token, public_key=public_key)
        root_path = options["root_path"] or "/"
        dry_run = options["dry_run"]
        overwrite = options["overwrite"]
        clear_video_url = options["clear_video_url"]
        include_inactive = options["include_inactive"]
        skip_space_check = options["skip_space_check"]
        course_filter = set(options["courses"] or [])

        course_qs = Course.objects.prefetch_related("modules")
        if not include_inactive:
            course_qs = course_qs.filter(is_active=True)
        if course_filter:
            course_qs = course_qs.filter(name__in=course_filter)

        courses_by_name = {course.name: course for course in course_qs}
        courses_by_normalized = {normalize_name(name): course for name, course in courses_by_name.items()}

        self.stdout.write(f"Yandex root: {root_path}")
        self.stdout.write(f"Mode: {'dry-run' if dry_run else 'sync'}")
        self.stdout.write(f"Courses in DB: {len(courses_by_name)}")

        course_dirs = [item for item in client.list_dir(root_path) if item.get("type") == "dir"]
        planned = []
        unmatched_dirs = []

        for course_dir in course_dirs:
            course = self._match_course(course_dir["name"], courses_by_name, courses_by_normalized)
            if not course:
                unmatched_dirs.append(course_dir["name"])
                continue

            videos = self._video_items(client, course_dir["path"])
            modules = list(course.modules.filter(is_active=True).order_by("order", "id"))
            if not modules:
                self.stdout.write(self.style.WARNING(f"No active modules in course: {course.name}"))
                continue

            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(f"{course.name}: {len(videos)} videos, {len(modules)} modules"))
            for module, video in zip(modules, videos):
                planned.append((course, module, video))
                self.stdout.write(
                    f"  #{module.order} {module.name} <- {video['name']} ({human_size(video.get('size') or 0)})"
                )

            for module in modules[len(videos):]:
                self.stdout.write(self.style.WARNING(f"  no video for module #{module.order} {module.name}"))
            for video in videos[len(modules):]:
                self.stdout.write(self.style.WARNING(f"  extra video without module: {video['name']}"))

        if unmatched_dirs:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Unmatched Yandex course folders:"))
            for name in unmatched_dirs:
                self.stdout.write(f"  - {name}")

        self.stdout.write("")
        self.stdout.write(f"Planned module video updates: {len(planned)}")
        planned_size = sum((video.get("size") or 0) for _, _, video in planned)
        self.stdout.write(f"Planned download size: {human_size(planned_size)}")
        if dry_run:
            return

        target_dir = Path(settings.PRIVATE_MEDIA_ROOT) / "education" / "videos"
        target_dir.mkdir(parents=True, exist_ok=True)
        if not skip_space_check:
            available = disk_available_bytes(target_dir)
            # Keep a small safety margin for temp files, logs, and database writes.
            required = planned_size * 1.05
            if available < required:
                raise CommandError(
                    "Not enough free space for LMS video sync: "
                    f"available {human_size(available)}, required about {human_size(required)}. "
                    "Free disk space, sync a smaller course with --course, or pass --skip-space-check if you know what you are doing."
                )

        updated = 0
        skipped = 0
        for _, module, video in planned:
            if module.private_video and not overwrite:
                skipped += 1
                self.stdout.write(f"SKIP existing private_video: module {module.id} {module.name}")
                continue

            filename = safe_filename(course_name=module.course.name, module=module, source_name=video["name"])
            tmp_path = None
            try:
                self.stdout.write(f"DOWNLOAD module {module.id}: {video['path']}")
                fd, tmp_path = tempfile.mkstemp(prefix="lms-yandex-", suffix=Path(filename).suffix)
                os.close(fd)
                client.download(video["path"], tmp_path)

                with transaction.atomic():
                    with open(tmp_path, "rb") as source:
                        module.private_video.save(filename, File(source), save=False)
                    if clear_video_url:
                        module.video_url = ""
                    module.save(update_fields=["private_video", "video_url", "updated_at"])
                updated += 1
                self.stdout.write(self.style.SUCCESS(f"OK module {module.id}: {module.private_video.name}"))
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            time.sleep(0.2)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Updated: {updated}; skipped: {skipped}"))

    def _match_course(self, folder_name, courses_by_name, courses_by_normalized):
        normalized = normalize_folder_name(folder_name)
        alias = COURSE_ALIASES.get(normalized)
        if alias and alias in courses_by_name:
            return courses_by_name[alias]
        return courses_by_normalized.get(normalized)

    def _video_items(self, client, path):
        items = client.list_dir(path)
        videos = [
            item
            for item in items
            if item.get("type") == "file" and is_video(item.get("name", ""), item.get("mime_type", ""))
        ]
        return sorted(videos, key=video_sort_key)

    def _clean_public_key(self, value):
        value = (value or "").strip()
        if not value:
            return ""
        return value.split("?", 1)[0]


def normalize_folder_name(value):
    value = value.strip().replace("ё", "е").lower()
    value = re.sub(r"^\s*\d+\s*[.)-]?\s*", "", value)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\bбазовый уровень\b", "базовый", value)
    value = re.sub(r"[-_]+", " ", value)
    value = re.sub(r"[^0-9a-zа-я]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value):
    value = value.strip().replace("ё", "е").lower()
    value = re.sub(r"[-_]+", " ", value)
    value = re.sub(r"[^0-9a-zа-я]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_video(name, mime_type):
    suffix = Path(name).suffix.lower()
    return suffix in VIDEO_EXTENSIONS or mime_type.startswith("video/")


def video_sort_key(item):
    name = item.get("name", "")
    match = re.search(r"(?:урок\s*№?\s*|урок\s+|lesson\s*)?(\d+)", name, re.IGNORECASE)
    lesson_number = int(match.group(1)) if match else 10_000
    return lesson_number, name.lower()


def safe_filename(course_name, module, source_name):
    suffix = Path(source_name).suffix.lower() or ".mp4"
    course_slug = slugify(course_name, allow_unicode=True) or f"course-{module.course_id}"
    module_slug = slugify(module.name, allow_unicode=True) or f"module-{module.id}"
    return f"{course_slug}/{module.order:02d}-{module.id}-{module_slug}{suffix}"


def human_size(size):
    size = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024


def disk_available_bytes(path):
    usage = os.statvfs(path)
    return usage.f_bavail * usage.f_frsize
