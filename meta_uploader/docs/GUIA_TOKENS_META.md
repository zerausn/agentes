# Guia de Tokens de Meta

Esta guia explica una ruta segura y general para preparar el subproyecto sin
guardar datos personales, nombres reales de cuentas o tokens dentro del repo.

## Principio base

- Instagram y Facebook no usan exactamente el mismo token operativo.
- La referencia oficial de Instagram Graph API documenta publicacion con token
  de usuario.
- Facebook Page video endpoints trabajan con token de pagina.
- Por eso este proyecto separa:
  - `META_IG_USER_TOKEN`
  - `META_FB_PAGE_TOKEN`
  - `META_PAGE_TOKEN` como variable de compatibilidad o bootstrap

## Variables del proyecto

- `META_PAGE_TOKEN`
  Token base para diagnostico inicial y algunas utilidades de descubrimiento.
- `META_IG_USER_TOKEN`
  Token preferido para publicar en Instagram.
- `META_FB_PAGE_TOKEN`
  Token de pagina para `/{page-id}/videos` y `/{page-id}/video_reels`.
- `META_FB_PAGE_ID`
  ID de la pagina de Facebook conectada.
- `META_IG_USER_ID`
  ID del usuario profesional de Instagram conectado a esa pagina.
- `META_APP_ID`
  Necesario solo para el flujo avanzado de file handles.

## Flujo recomendado

1. Crea o reutiliza una app de Meta for Developers con los permisos oficiales
   que realmente necesitas.
2. Obtiene un token base con alcance suficiente para listar paginas y leer la
   conexion con Instagram.
3. Usa `python get_meta_ids.py` para descubrir `META_FB_PAGE_ID` y
   `META_IG_USER_ID`.
4. Usa `python get_page_token.py` si necesitas derivar `META_FB_PAGE_TOKEN`
   desde el token base.
5. Guarda los valores solo en `.env`, nunca en Markdown, logs ni commits.

## Permisos que normalmente intervienen

- `pages_manage_posts`
- `pages_read_engagement`
- `instagram_basic`
- `instagram_content_publish`

Antes de pedir mas permisos, confirma si el endpoint realmente los necesita.

## Verificaciones utiles

- `python debug_token.py`
  Para revisar el diagnostico del token actual.
- `python check_page_v2.py`
  Para comprobar que el page token puede leer la pagina y el edge de videos.

## Recomendaciones de seguridad

- No publiques tokens en issues, PRs, docs ni capturas.
- No dejes nombres de negocios, correos o IDs reales en la documentacion del
  repo.
- Si un token se filtra, revocalo y genera uno nuevo.
- Mantiene 2FA y Page Publishing Authorization al dia en la cuenta y pagina
  conectadas.
- Si vas a correr `test_batch_upload.py` o `test_batch_upload_v2.py`, habilita
  primero `META_ENABLE_UPLOAD=1` de forma consciente.
