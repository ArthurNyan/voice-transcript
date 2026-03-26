# Voice Transcript

Веб-приложение для транскрибации голоса и аудиофайлов через `faster-whisper`. Работает локально и в облаке (Railway).

## Возможности

- запись с микрофона в браузере;
- загрузка аудиофайлов;
- транскрибация на русском языке;
- фоновая обработка длинных записей;
- прогресс-бар по этапам обработки;
- экспорт результата в `TXT` и `JSON`.

## Требования

- Python 3.9+
- `ffmpeg`

Установка `ffmpeg` на macOS:

```bash
brew install ffmpeg
```

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

После запуска откройте [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Конфигурация

Сейчас приложение использует дефолтную модель `small` и русский язык `ru`.
Следующим шагом можно вынести конфигурацию через переменные окружения без изменения API.

Поддерживаемые переменные окружения:

- `WHISPER_MODEL_SIZE` — размер модели, по умолчанию `small`
- `WHISPER_COMPUTE_TYPE` — тип вычислений для `faster-whisper`, по умолчанию `default`
- `TRANSCRIPT_LANGUAGE` — язык транскрибации, по умолчанию `ru`
- `TEMP_DIR` — директория для временных файлов, по умолчанию `tmp`
- `MAX_UPLOAD_SIZE_MB` — лимит размера загружаемого файла, по умолчанию `100`
- `MAX_AUDIO_DURATION_MINUTES` — лимит длины аудио для синхронной обработки, по умолчанию `10`
- `CHUNK_DURATION_SECONDS` — длительность одного чанка для фоновой обработки, по умолчанию `60`

## Деплой на Railway

Railway — оптимальный выбор: поддерживает Docker, нет таймаутов, можно подключить persistent volume для кэша модели.

### Шаги

1. Запушить репозиторий на GitHub.

2. Зайти на [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo** → выбрать репозиторий.

3. Railway автоматически обнаружит `Dockerfile` и соберёт образ.

4. После деплоя зайти в **Settings → Networking → Generate Domain** — получить публичный URL.

### Persistent volume (рекомендуется)

Без volume модель Whisper будет скачиваться (~460 MB) при каждом перезапуске контейнера.

Чтобы этого избежать:

1. В Railway: **Add Service → Volume** → смонтировать в `/data`.
2. Добавить переменную окружения `HF_HOME=/data/huggingface` (уже установлена в `Dockerfile`).

### Переменные окружения на Railway

Задаются в разделе **Variables** проекта:

| Переменная | Описание | По умолчанию |
|---|---|---|
| `WHISPER_MODEL_SIZE` | Размер модели (`tiny`, `small`, `medium`) | `small` |
| `WHISPER_COMPUTE_TYPE` | Тип вычислений | `default` |
| `TRANSCRIPT_LANGUAGE` | Язык транскрибации | `ru` |
| `MAX_UPLOAD_SIZE_MB` | Лимит загрузки (MB) | `100` |

> **Ресурсы:** модель `small` требует ~1.5 GB RAM. Для Railway Hobby-плана этого достаточно.

## API

Короткие записи обрабатываются синхронно через `POST /api/transcribe`.
Длинные записи — через job-based API:

- `POST /api/jobs` — создать задачу;
- `GET /api/jobs/{job_id}` — получить статус и прогресс;
- `GET /api/jobs/{job_id}/result` — получить готовый результат.

Веб-интерфейс использует именно этот режим и показывает прогресс по шагам.
