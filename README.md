# Python_Autumn_2026

Backend-реализация лабораторных работ 1 и 2.

- ЛР 1: приём, валидация и расширяемые анализаторы студенческих работ.
- ЛР 2: сервис сравнения сходства для backend-трека.

## Что реализовано

- Python-пакет `lab1_backend` в `src`-layout.
- Pydantic-модели входных данных отдельно от immutable domain-моделей.
- In-memory репозиторий приёма работ с обработкой дублей и конфликтов.
- In-memory и JSONL-источники студенческих работ.
- Потоковые JSONL-итераторы для сравнения в ЛР 2.
- JSON-источник заданий.
- Реестр анализаторов с `LengthAnalyzer`, `TemplateAnalyzer` и `AIDeclarationAnalyzer`.
- Сервис сравнения для ЛР 2:
  - удаление комментариев и нормализация пробелов;
  - извлечение точных 3-грамм;
  - Jaccard similarity;
  - top-k похожих работ;
  - фильтрация по заданию и исключение self-match;
  - пометка повторных версий одного студента;
  - отделение разрешённых шаблонов;
  - стратегии `full_scan` и простой `ngram_index`;
  - кеш признаков по содержимому работы, шаблонам задания и конфигурации анализатора.
- Утилиты экспериментов для ЛР 2:
  - оценка качества по размеченным парам;
  - confusion matrix, precision, recall, F1;
  - доля uncertain-результатов;
  - benchmark wall time и peak memory на синтетическом нагрузочном корпусе.
- Тесты для intake, анализаторов, сравнения, streaming, поведения индекса и метрик.

## Структура проекта

```text
src/lab1_backend/
  analysis.py
  bootstrap.py
  comparison.py
  domain.py
  exceptions.py
  experiments.py
  intake.py
  protocols.py
tests/
examples/
  assignments.json
  submissions.jsonl
  invalid_submissions.jsonl
  lab2_assignments.json
  lab2_submissions.jsonl
  lab2_labels.json
  generate_lab2_large_dataset.py
  lab2_large_submissions.jsonl
  lab2_large_labels.json
```

## Требования

- Python 3.11+

## Установка

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

## Запуск тестов

```bash
.venv/bin/python -m pytest
```

## Запуск анализаторов ЛР 1

Запуск анализаторов по умолчанию:

```bash
.venv/bin/python -m lab1_backend analyze
```

Старая форма запуска без подкоманды тоже поддерживается:

```bash
.venv/bin/python -m lab1_backend
```

Запуск одного анализатора:

```bash
.venv/bin/python -m lab1_backend analyze --analyzer template
```

Свои входные файлы:

```bash
.venv/bin/python -m lab1_backend analyze \
  --assignments examples/assignments.json \
  --submissions examples/submissions.jsonl
```

## Запуск сравнения ЛР 2

Сравнение полным перебором:

```bash
.venv/bin/python -m lab1_backend compare \
  --assignments examples/lab2_assignments.json \
  --submissions examples/lab2_large_submissions.jsonl \
  --submission-id large-0001 \
  --top-k 5 \
  --strategy full_scan
```

Фильтрация кандидатов через n-gram index:

```bash
.venv/bin/python -m lab1_backend compare \
  --assignments examples/lab2_assignments.json \
  --submissions examples/lab2_large_submissions.jsonl \
  --submission-id large-0001 \
  --top-k 5 \
  --strategy ngram_index
```

Вывод — JSON. Для каждого совпадения возвращаются:

- `submission_id` кандидата;
- `student_id`;
- `same_student`;
- Jaccard `similarity`;
- размеры intersection/union;
- `review_required`;
- `insufficient_data`;
- evidence с диапазонами строк;
- metadata метода.

Similarity используется только как сигнал для ручной проверки. Это не доказательство плагиата или нарушения.

## Эксперименты ЛР 2

Запуск метрик качества и измерений производительности:

```bash
.venv/bin/python -m lab1_backend experiment \
  --assignments examples/lab2_assignments.json \
  --submissions examples/lab2_large_submissions.jsonl \
  --labels examples/lab2_large_labels.json \
  --sizes 100 1000 5000 \
  --repeats 3 \
  --seed 42
```

Команда experiment использует:

- `examples/lab2_large_labels.json` для сгенерированных размеченных пар качества;
- детерминированное расширение корпуса для нагрузочных измерений.

Синтетический корпус используется только для измерения скорости и памяти. Метрики качества считаются на размеченных примерах. Для `ngram_index` построение индекса измеряется отдельно, а query latency считается по заранее построенному индексу — так же, как в backend-системе, где индекс готовится до обработки запросов.

## Данные для ЛР 2

- `examples/lab2_assignments.json` — metadata заданий и разрешённые шаблоны.
- `examples/lab2_submissions.jsonl` — компактный ручной корпус из 16 работ.
- `examples/lab2_labels.json` — компактные размеченные пары для оценки качества.
- `examples/generate_lab2_large_dataset.py` — детерминированный генератор большого датасета.
- `examples/lab2_large_submissions.jsonl` — сгенерированный корпус из 421 работы.
- `examples/lab2_large_labels.json` — сгенерированная разметка из 331 пары.

Перегенерировать большой датасет:

```bash
.venv/bin/python examples/generate_lab2_large_dataset.py
```

Запустить эксперименты на большом датасете:

```bash
.venv/bin/python -m lab1_backend experiment \
  --assignments examples/lab2_assignments.json \
  --submissions examples/lab2_large_submissions.jsonl \
  --labels examples/lab2_large_labels.json \
  --sizes 100 1000 5000 \
  --repeats 3 \
  --seed 42
```

Компактный ручной корпус покрывает:

- идентичный код;
- переименованные переменные;
- независимые решения;
- совпадение только по разрешённому шаблону;
- пустой ввод;
- ввод только из комментариев;
- `SyntaxError`;
- исключение self-match;
- повторные версии одного студента;
- фильтрацию между разными заданиями.

## Примечания

- Domain layer не читает `stdin`, не делает HTTP-вызовы и не выполняет пользовательский код.
- Отправленный код токенизируется как текст и никогда не исполняется.
- Совпадения только по шаблону отделяются от подозрительных 3-грамм.
- Пустые/comment-only работы возвращают `insufficient_data`, а не искусственный нулевой score.
- Full scan потоково читает кандидатов из JSONL, а n-gram index намеренно материализует inverted index и отдельно сообщает число кандидатов.
