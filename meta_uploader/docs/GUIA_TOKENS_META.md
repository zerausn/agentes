# Guía de Generación de Tokens (Meta Graph API)

Basado en tu configuración actual, ya tienes lo más difícil resuelto: La cuenta de Instagram **@performaticwritingscali** está enlazada correctamente a la página **Performatic Writings Cali**, todo bajo tu portafolio empresarial **Cali escriturasperformaticas**.

Para conectar nuestro script automatizado sin que tu sesión expire cada poco tiempo, usaremos la estrategia del **Usuario del Sistema (System User)**, que genera un Token Permanente.

## Paso 1: Crear la App de Desarrollador
1. Ingresa a [Meta for Developers](https://developers.facebook.com/) asegurándote de haber iniciado sesión con tu cuenta personal (`zerausn@gmail.com`).
2. Ve a **Mis apps (My Apps)** en el menú superior.
3. Haz clic en **Crear app (Create App)**.
4. Elije el tipo de app: Selecciona **"Otro" (Other)** y luego selecciona **"Empresa" (Business)**.
5. Nombra tu app (ej: `Uploader_Scripter`).
6. En la opción **"Cuenta comercial de facturación/portafolio"**, **DEBES abrir el menú desplegable y elegir "Cali escriturasperformaticas"**.
7. Haz clic en Crear app. Te pedirá tu contraseña de Facebook.

## Paso 2: Crear el Usuario del Sistema (Token Permanente)
1. Ahora vamos a tu Suite Empresarial. Ve directamente a [Configuración del Negocio (Business Settings)](https://business.facebook.com/settings).
2. En la columna izquierda, dentro de **Usuarios**, haz clic en **Usuarios del sistema (System Users)**.
3. Haz clic en **Añadir (Add)**. Nombre: `Uploader Bot`. Rol: **Administrador (Admin)**. Luego "Crear".
4. Selecciona tu nuevo `Uploader Bot` recién creado y haz clic en **"Añadir activos (Add Assets)"**.
   - En la pestaña **Páginas (Pages)**: Selecciona "Performatic Writings Cali" y enciéndele el interruptor de **Control Total (Full Control)** hacia la derecha.
   - En la pestaña **Cuentas de Instagram**: Selecciona "@performaticwritingscali" y enciéndele las opciones para crear contenido. Guarda los cambios.

## Paso 3: Generar el Token y Obtener Permisos
1. Teniendo seleccionado tu usuario del sistema (`Uploader Bot`), haz clic en el botón **Generar nuevo token (Generate New Token)** (está arriba a la derecha).
2. Te pedirá elegir la App (selecciona la app `Uploader_Scripter` que creamos en el Paso 1).
3. **¡IMPORTANTE!** En la lista de permisos (Permissions) busca y marca las siguientes cuatro casillas:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
4. Haz clic en **Generar token**.
5. Te aparecerá un texto muy largo (una cadena alfanumérica). **¡Cópialo inmediatamente y guárdalo!** Facebook no te lo volverá a mostrar. Este es tu `META_PAGE_TOKEN`. Pégalo en tu archivo `.env`.

## Paso 4: Obtener tu IG_USER_ID y FB_PAGE_ID
Ya tienes la llave, ahora necesitamos las puertas.
1. Ve a la herramienta [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. En la casilla principal que dice **"Access Token"**, borra lo que haya y **pega el token largo** que acabas de copiar en el Paso 3. Puedes darle Enter para validar.
3. **Para obtener el FB_PAGE_ID**: 
   - En la barra de búsqueda (GET), escribe `me/accounts` y dale a "Submit". A la derecha te mostrará un JSON con el "id" de tu página "Performatic Writings Cali". Pega ese número en `.env` bajo `META_FB_PAGE_ID`.
4. **Para obtener el IG_USER_ID**: 
   - Ahora, en la barra de búsqueda escribe: `{Pega-aqui-tu-FB_PAGE_ID}?fields=instagram_business_account`
   - (Ejemplo: `10023456789?fields=instagram_business_account`)
   - Dale buscar. El JSON te devolverá el `"id"` exclusivo de la cuenta de Instagram. Pégalo en `.env` bajo `META_IG_USER_ID`.

---
¡Listo! Ya has enlazado e inicializado la infraestructura oficial necesaria para que `meta_uploader.py` tome el control.
