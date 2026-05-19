# SavdoPro

POS va ombor boshqaruvi (Vue 3 + Django + PostgreSQL). Offline kassa qo‘llab-quvvatlanadi.

## Tez boshlash (Docker)

```bash
cp .env.example .env
# .env ichida DJANGO_SECRET_KEY ni o‘zgartiring

docker compose up --build
```

- Frontend: https://localhost:51711  
- Backend API: http://localhost:8011/api/v1/  
- Admin: http://localhost:8011/admin/

(Lokal va prod bir xil portlar: `.env` da `51711`, `8011`, `54311`.)

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

1. Serverda: `cp .env.production.example .env` — `SERVER_IP` va parollarni to‘ldiring.
2. Yoki `.env.example` dan nusxa olib production portlarini qo‘ying (quyida).
3. `docker compose up -d --build`

**Muhim:** `DB_PORT=5432` (ichki). `POSTGRES_PUBLISH_PORT=54311` — faqat hostdan kirish; `DB_PORT` ga qo‘ymang.

Brauzer: `https://SERVER-IP:51711` · API: `http://SERVER-IP:8011/api/v1/` (lokal bilan bir xil)

### DB ulanish xatosi

```bash
docker compose ps
docker compose exec backend env | grep -E '^DB_|PUBLISH'
```

`DB_HOST=db`, `DB_PORT=5432` bo‘lishi kerak.

## Offline sinov

Backendni o‘chirish yetadi (frontend ishlashi kerak):

```bash
docker compose stop backend
```
