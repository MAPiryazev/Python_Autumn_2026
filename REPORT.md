# Отчёт по ЛР 1 и ЛР 2

## Трек

- Трек: Backend
- ЛР 1: приём работ и архитектура анализаторов
- ЛР 2: сравнение сходства и оценка качества

## Реализованные требования ЛР 1

- Устанавливаемый пакет в `src`-layout.
- Immutable domain-модели и типизированный public API.
- Pydantic-модели для валидации входных данных.
- Отдельный intake adapter и domain service.
- In-memory репозиторий работ.
- Обнаружение дублей и конфликтов по `submission_id` и хешу payload.
- JSONL batch import, который продолжает обработку после битых строк.
- Протокол анализатора и реестр анализаторов.
- `LengthAnalyzer`, `TemplateAnalyzer` и `AIDeclarationAnalyzer`.
- In-memory и JSONL-источники работ.
- Источник заданий из JSON.
- Сборка конфигурации без глобального mutable container state.
- Воспроизводимый запуск через `python -m lab1_backend analyze`.

## Реализованные требования ЛР 2

### Сервис сравнения

Backend-реализация ЛР 2 добавляет сервис сравнения, независимый от слоёв хранения и API.

Реализованное поведение:

- читает работы из JSONL;
- поддерживает потоковую итерацию через `iter_submissions()` и `iter_by_assignment()`;
- фильтрует кандидатов по `assignment_id`;
- исключает точный self-match по `submission_id`;
- сохраняет повторные версии одного студента, но помечает их через `same_student=True`;
- возвращает top-k совпадений;
- отделяет совпадение по разрешённому шаблону от подозрительного сходства;
- сохраняет evidence как диапазоны строк исходного текста;
- сообщает similarity как сигнал для review, а не как доказательство нарушения.

### Извлечение признаков

Для Python-кода сервис:

1. токенизирует код через стандартный модуль `tokenize`, где это возможно;
2. игнорирует комментарии, indentation, newlines и encoding/end markers;
3. для невалидного синтаксиса использует консервативную текстовую токенизацию;
4. нормализует идентификаторы до `<identifier>`;
5. нормализует числовые литералы до `<number>`;
6. нормализует строковые литералы до `<string>`;
7. строит точные 3-граммы;
8. сохраняет evidence по строкам для общих подозрительных 3-грамм.

Разрешённые шаблонные строки из `Assignment.allowed_templates` помечаются отдельно. Совпадения только по шаблону возвращают `insufficient_data=True` для подозрительной similarity и не требуют review.

### Similarity

Метод сходства — exact 3-gram Jaccard:

```text
similarity = |left ∩ right| / |left ∪ right|
```

Если union пустой, score равен `null`, а результат помечается как `insufficient_data`. Реализация не подменяет недостаток данных значением `0.0`.

### Стратегии кандидатов

Реализованы две стратегии:

1. `full_scan`
   - сравнивает целевую работу со всеми кандидатами того же задания, кроме самой себя.
2. `ngram_index`
   - строит простой inverted index `ngram -> submission_id set`;
   - сравнивает только кандидатов, у которых есть хотя бы одна общая подозрительная 3-грамма с target;
   - сообщает `index_version`, размер корпуса, число кандидатов и число отфильтрованных работ.

Текущая версия индекса: `ngram-index-v1`.

### Кеш

Извлечение признаков кешируется по ключу, основанному на:

- хеше содержимого работы;
- id задания;
- разрешённых шаблонах;
- версии анализатора;
- хеше конфигурации сравнения.

Изменение размера n-грамм, списка шаблонов, content hash, стратегии или версии анализатора инвалидирует ключ.

## Датасет ЛР 2

В проекте используются собственные датасеты вместо скачивания внешних студенческих работ.

Файлы компактного ручного датасета:

- `examples/lab2_assignments.json`
- `examples/lab2_submissions.jsonl`
- `examples/lab2_labels.json`

Файлы большого сгенерированного датасета:

- `examples/generate_lab2_large_dataset.py`
- `examples/lab2_large_submissions.jsonl`
- `examples/lab2_large_labels.json`

Генератор детерминированный и использует seed `20261108`. Он создаёт 421 работу и 331 размеченную пару по задачам factorial, palindrome, Fibonacci, prime checking, vowel counting, sorting, GCD и bracket-balance. Сгенерированный датасет включает варианты с переименованными переменными, комментариями, изменёнными пробелами, независимыми алгоритмами, повторными версиями одного студента, template-only случаями, empty/comment-only случаями и невалидным синтаксисом.

Компактный ручной корпус содержит 16 работ и покрывает:

- идентичный код;
- переименованные переменные;
- добавленные комментарии к тому же коду;
- независимые решения factorial;
- независимые решения palindrome;
- совпадение только по разрешённому шаблону;
- пустой ввод;
- ввод только из комментариев;
- невалидный синтаксис;
- повторную версию одного студента;
- похожий код из другого задания.

Компактный файл разметки содержит 11 пар с ground truth `review_required` и пояснением relation. Большой сгенерированный файл разметки содержит 331 пару. В финальном эксперименте ниже метрики качества считаются на `examples/lab2_large_labels.json`, а benchmark-корпуса детерминированно генерируются из `examples/lab2_large_submissions.jsonl`.

## Оценка качества

Параметры:

- threshold для review: `0.65`
- размер n-грамм: `3`
- основной датасет качества: `examples/lab2_large_labels.json`
- оценено пар: `331`

Результат на компактном размеченном датасете:

| Метрика | Значение |
| --- | ---: |
| TP | 4 |
| FP | 0 |
| TN | 7 |
| FN | 0 |
| Precision | 1.0 |
| Recall | 1.0 |
| F1 | 1.0 |
| Uncertain share | 0.1818 |

Результат на большом сгенерированном размеченном датасете:

| Метрика | Значение |
| --- | ---: |
| Оценено пар | 331 |
| TP | 240 |
| FP | 0 |
| TN | 91 |
| FN | 0 |
| Precision | 1.0 |
| Recall | 1.0 |
| F1 | 1.0 |
| Uncertain share | 0.0060 |

Uncertain-результаты ожидаемы для template-only и empty/comment-only пар, потому что в них недостаточно подозрительного содержимого для scoring.

## Оценка производительности

Форма команды:

```bash
.venv/bin/python -m lab1_backend experiment \
  --assignments examples/lab2_assignments.json \
  --submissions examples/lab2_large_submissions.jsonl \
  --labels examples/lab2_large_labels.json \
  --sizes 100 1000 5000 \
  --repeats 3 \
  --seed 42
```

Профиль корпуса: размеченные примеры для оценки качества; детерминированные синтетические копии и варианты для нагрузочных измерений.

N-gram index рассматривается как заранее построенная backend-структура. Поэтому benchmark разделяет:

- время построения индекса — измеряется и указывается отдельно;
- query time по готовому индексу — используется для сравнения latency full scan и index.

Для indexed-стратегии peak memory в таблице — это дополнительная query-time peak memory после того, как индекс уже построен. Время построения индекса вынесено в отдельную колонку.

### Измерения

| Size | Strategy | Timing scope | Comparisons | Median query time, s | Average query time, s | Median peak query memory, bytes | Average peak query memory, bytes | Median index build time, s |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | full_scan | full scan query | 99 | 0.0766 | 0.0763 | 985,492 | 986,297 | — |
| 100 | ngram_index | query on prebuilt index | 99 | 0.0056 | 0.0056 | 45,967 | 45,991 | 0.0175 |
| 1000 | full_scan | full scan query | 999 | 0.8352 | 0.8345 | 10,061,890 | 10,040,514 | — |
| 1000 | ngram_index | query on prebuilt index | 995 | 0.0563 | 0.0564 | 478,656 | 500,592 | 0.1886 |
| 5000 | full_scan | full scan query | 4999 | 4.9460 | 4.8616 | 50,246,591 | 50,246,660 | — |
| 5000 | ngram_index | query on prebuilt index | 4972 | 0.2994 | 0.2995 | 2,716,752 | 2,716,752 | 1.1233 |

### Интерпретация

Заранее построенный n-gram index уменьшает число точных сравнений на синтетическом корпусе:

- 100 записей: 99 -> 99 кандидатов;
- 1000 записей: 999 -> 995 кандидатов;
- 5000 записей: 4999 -> 4972 кандидата.

Так как построение индекса моделируется как offline/precomputed backend-этап, query latency для indexed search значительно ниже:

- 100 записей: median 0.0766 s -> 0.0056 s;
- 1000 записей: median 0.8352 s -> 0.0563 s;
- 5000 записей: median 4.9460 s -> 0.2994 s.

В отчёте всё равно отдельно указано время построения индекса, чтобы измерение было воспроизводимым и честным. Это не смешивает offline indexing cost с online query latency.

## Команды проверки

Успешно выполнено:

```bash
.venv/bin/python -m pytest
```

Результат:

```text
31 passed
```

Также успешно выполнено:

```bash
.venv/bin/python -m lab1_backend analyze

.venv/bin/python -m lab1_backend compare \
  --assignments examples/lab2_assignments.json \
  --submissions examples/lab2_large_submissions.jsonl \
  --submission-id large-0001 \
  --top-k 5 \
  --strategy full_scan

.venv/bin/python -m lab1_backend compare \
  --assignments examples/lab2_assignments.json \
  --submissions examples/lab2_large_submissions.jsonl \
  --submission-id large-0001 \
  --top-k 5 \
  --strategy ngram_index

.venv/bin/python -m lab1_backend experiment \
  --assignments examples/lab2_assignments.json \
  --submissions examples/lab2_large_submissions.jsonl \
  --labels examples/lab2_large_labels.json \
  --sizes 100 1000 5000 \
  --repeats 3 \
  --seed 42
```
