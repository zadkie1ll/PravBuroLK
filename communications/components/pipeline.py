# Вебхук с файлом-> Транскрибция -> Анализ -> Логирование -> Сохранение в БД 
                                                                        #
#                                                            Если все плохо, отправить увед
from ai import transcribe, ai_analysis
import logging
def pipeline(file):
    transcribed = transcribe(file)
    analysis = ai_analysis(transcribed)
    logging.INFO("Пройденный анализ")