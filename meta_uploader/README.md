# Meta Uploader Agent (Facebook & Instagram)

Este directorio contiene el automatizador de Graph API de Meta, inspirado en
la separacion arquitectonica de `youtube_uploader`.

## Estado

En desarrollo. El objetivo es publicar Reels y videos estandar hacia Facebook e
Instagram con manejo de limites, polling de contenedores y calendario propio.

## Setup rapido

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edita .env con tus credenciales reales
python meta_uploader.py
```

## Variables esperadas

- `META_PAGE_TOKEN`
- `META_IG_USER_ID`
- `META_FB_PAGE_ID`

## Notas

- `.env`, logs y caches locales no se deben subir a Git.
- La implementacion funcional sigue en curso; revisa `AI.md` y `docs/` antes de
  cambiar este subproyecto.
