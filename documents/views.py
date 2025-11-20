import os
import logging
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render
from django.conf import settings
from .services.document_pipeline import DocumentPipeline

logger = logging.getLogger(__name__)


def generate_document(request):
    if request.method != "POST":
        raise Http404("Этот эндпоинт принимает только POST-запросы.")

    context = request.POST.dict()

    template_path = os.path.join(
        settings.BASE_DIR,
        "documents",
        "templates_src",
        "base_template.docx"
    )

    if not os.path.exists(template_path):
        return JsonResponse({
            "error": "Шаблон .docx не найден.",
            "path": template_path
        })

    output_dir = os.path.join(settings.MEDIA_ROOT, "generated_docs")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "generated_document.docx")

    pipeline = DocumentPipeline(template_path, context)
    pipeline.run()
    pipeline.save(output_path)

    with open(output_path, "rb") as file:
        response = HttpResponse(
            file.read(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        response['Content-Disposition'] = 'attachment; filename="generated_document.docx"'
        return response


def document_form(request):
    """
    Просто рендерит страницу — форма должна отправлять в generate_document.
    """
    return render(request, "document_form.html")
