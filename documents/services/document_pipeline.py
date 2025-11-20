# documents/services/document_pipeline.py

from docxtpl import DocxTemplate
import logging

logger = logging.getLogger(__name__)

class DocumentPipeline:
    """
    Универсальный pipeline для генерации документов.
    Он управляет цепочкой шагов (handlers), которые последовательно
    модифицируют документ, а в конце подставляет переменные в шаблон.
    """

    def __init__(self, template_path, context):
        """
        :param template_path: путь к шаблону .docx
        :param context: словарь с данными для подстановки
        """
        self.doc = DocxTemplate(template_path)
        self.context = context
        self.steps = []

    def add_step(self, step):
        """
        Добавляет шаг в пайплайн.
        :param step: функция или объект с __call__(doc, context)
        """
        self.steps.append(step)
        return self

    def run(self):
        """
        Запускает все шаги пайплайна последовательно,
        а затем рендерит шаблон с подстановкой переменных.
        """
        for step in self.steps:
            try:
                step(self.doc, self.context)
            except Exception as e:
                logger.exception(f"Ошибка на шаге {step}: {e}")

        # Важный вызов: подставляем переменные в шаблон
        try:
            self.doc.render(self.context)
        except Exception as e:
            logger.exception(f"Ошибка при рендере шаблона: {e}")
            raise

        return self

    def save(self, output_path):
        """
        Сохраняет готовый документ.
        :param output_path: путь для сохранения .docx
        """
        try:
            self.doc.save(output_path)
        except Exception as e:
            logger.exception(f"Ошибка при сохранении документа: {e}")
            raise
        return output_path