# Обёртка над Keitaro

Тестовое задание: веб-приложение поверх Admin API Keitaro.

## Что умеет

1. **Создаватор кампаний** — принимает название, гео-код страны и ID оффера.
   Создаёт в Keitaro кампанию с двумя потоками:
   - поток 1: фильтр по стране (гео) → редирект на `https://google.com`;
   - поток 2: выбранный оффер (share 100%).
   Домен, группа и источник трафика подставляются из API (группа `adrobot` создаётся автоматически, если её нет).
2. **Редактор кампаний** — открывает потоки кампании, позволяет добавлять и удалять офферы в офферном потоке. Доли автоматически пересчитываются так, чтобы в сумме было ровно 100%.

## Стек

- Backend: FastAPI + SQLAlchemy (SQLite) + httpx
- Frontend: React + Vite
- Docker / docker-compose

## Запуск одной командой

```bash
docker compose up --build
```

- Фронтенд: http://localhost:5173
- Backend API: http://localhost:8000/docs

Настройки читаются из `.env` (см. `.env.example`):

- `KEITARO_BASE_URL` — адрес трекера;
- `KEITARO_API_KEY` — API-ключ из админки Keitaro (Account → API keys).

## API обёртки

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api/meta` | офферы, домены, группы для селектов |
| POST | `/api/campaigns` | создать кампанию `{name, geo, offer_id}` |
| GET | `/api/campaigns` | список кампаний Keitaro |
| GET | `/api/campaigns/{id}/streams` | потоки кампании с офферами |
| POST | `/api/campaigns/{id}/streams/{sid}/offers` | добавить оффер в поток |
| DELETE | `/api/campaigns/{id}/streams/{sid}/offers/{oid}` | удалить оффер из потока |

Локально (без Docker): `pip install -r backend/requirements.txt && uvicorn app.app:app --app-dir backend --port 8000`.

## Заметки по Keitaro API

- Кампании создаются через `POST /admin_api/v1/campaigns`, потоки передаются в поле `streams`.
- Редактирование офферов потока — `PUT /admin_api/v1/streams/{id}` (полный payload потока + массив `offers`).
- Удаление кампании — `DELETE /admin_api/v1/campaigns/{id}` (soft delete, `state: deleted`).
