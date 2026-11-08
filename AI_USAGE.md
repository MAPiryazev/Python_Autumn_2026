# AI_USAGE

Проект не использует AI-модель во время выполнения.

AI-помощь использовалась только как вспомогательный инструмент разработки. Она помогла:

- интерпретировать требования лабораторной работы;
- подготовить план backend-реализации ЛР 2;
- предложить тестовые сценарии для сравнения сходства;
- подготовить структуру собственного размеченного датасета;
- набросать детерминированные варианты для большого generated dataset в ЛР 2;
- подготовить текст документации и отчёта.

Runtime-реализация сама по себе детерминированная и локальная:

- пакет не вызывает внешние AI-сервисы;
- сравнение использует токенизацию, точные 3-граммы, Jaccard similarity и детерминированную фильтрацию кандидатов;
- генерация benchmark-данных использует фиксированный seed.

Финальная реализация была вручную проверена и скорректирована под требования backend-трека.

Главный фокус работы — поведение итогового проекта:

- пакет корректно устанавливается;
- intake/analyzer workflow запускается на примерах ЛР 1;
- workflow сравнения ЛР 2 запускается на собственном датасете;
- доступны стратегии `full_scan` и `ngram_index`;
- формируются метрики качества по разметке и воспроизводимые benchmark-результаты;
- обязательные сценарии покрыты автоматическими тестами.

Готовность проекта перед сдачей проверялась воспроизводимыми командами:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m lab1_backend analyze
.venv/bin/python -m lab1_backend compare --assignments examples/lab2_assignments.json --submissions examples/lab2_large_submissions.jsonl --submission-id large-0001 --top-k 5 --strategy full_scan
.venv/bin/python -m lab1_backend compare --assignments examples/lab2_assignments.json --submissions examples/lab2_large_submissions.jsonl --submission-id large-0001 --top-k 5 --strategy ngram_index
.venv/bin/python -m lab1_backend experiment --assignments examples/lab2_assignments.json --submissions examples/lab2_large_submissions.jsonl --labels examples/lab2_large_labels.json --sizes 100 1000 5000 --repeats 3 --seed 42
```
