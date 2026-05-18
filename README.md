# SavdoPro

POS va ombor boshqaruvi (Vue 3 + Django + PostgreSQL). Offline kassa qo‘llab-quvvatlanadi.

## Tez boshlash (Docker)

```bash
cp .env.example .env
# .env ichida DJANGO_SECRET_KEY ni o‘zgartiring

docker compose up --build
```

- Frontend: https://localhost:5173  
- Backend API: http://localhost:8000/api/v1/  
- Admin: http://localhost:8000/admin/

## Git — nima commit qilinadi?

| Fayl | Gitga? |
|------|--------|
| `backend/savdopro/settings.py` | **Ha** — kod (maxfiy qiymatlar `.env` da) |
| `.env` | **Yo‘q** — `.gitignore` da |
| `.env.example` | **Ha** — namuna |
| `settings_local.py` | **Yo‘q** — shaxsiy override |
| `backend/media/` | **Yo‘q** — yuklangan rasmlar |
| `node_modules/`, `frontend/dist/` | **Yo‘q** |
| `.venv/` | **Yo‘q** |

## Birinchi marta repo

```bash
git init
git add .
git status   # .env va media ko‘rinmasligi kerak
git commit -m "Initial commit: SavdoPro POS"
```

## Serverga deploy

1. `.env` ni serverda yarating (`DJANGO_DEBUG=False`, kuchli `DJANGO_SECRET_KEY`).
2. `docker compose up -d --build`
3. Migratsiya: `docker compose exec backend python manage.py migrate`

## Offline sinov

Backendni o‘chirish yetadi (frontend ishlashi kerak):

```bash
docker compose stop backend
```
