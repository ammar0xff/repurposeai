# Development

```bash
pip install -e ".[dev]"      # backend + lint + tests (+[stt] for whisper, +[s3])
alembic upgrade head
uvicorn app.main:app --reload
pytest -q                    # unit (anywhere) + integration (needs backend deps)
ruff check app tests scripts && mypy app
cd web && npm install && npm run dev   # vite :5173 proxies /api to :8000
```

Conventions: pipeline modules stay stdlib-only (their tests run without the
backend installed). Pydantic/SQLAlchemy/FastAPI live at API/DB boundary.
`make` targets wrap the common flows. Pre-commit not enforced; CI is.
