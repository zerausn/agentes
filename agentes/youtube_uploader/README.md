# Youtube Auto-Uploader (Performatic Writings)

Este repositorio contiene las herramientas creadas mediante AI Agents (Antigravity) para buscar los videos de eventos y producciones teatrales (\`.mp4\`, \`.mkv\`) más pesados en la computadora y automatizar de manera oficial su subida a YouTube para la cuenta de *zerausn*.

## ¿Por qué esta solución?

YouTube restringe el uso masivo de su API. La cuota por defecto por cada **proyecto de Google Cloud** es de `10,000` unidades, y subir un solo video cuesta `1,600` unidades (máximo de 6 videos al día). Para evitar el riesgo altísimo de que baneen los canales por usar bots clandestinos en navegadores, hemos construido este programa que usa la **API Oficial de Google** y rota entre 2 o 3 proyectos (creados en tu misma cuenta de Google) cuando se acaba la cuota diaria de uno de ellos, alcanzando así el objetivo de subir *15 a 18 videos* cada 24 horas.

## Estructura del Proyecto

- `video_scanner.py`: Escanea el disco duro (omitiendo archivos de sistema y descargas livianas) para crear una base de datos de los videos pesados en la PC (mayores a 100MB).
- `uploader.py`: Lee la base de datos de videos encontrados, revisa el estado de subida (evita procesar duplicados) y aplica OAuth 2.0. Hace chunked uploads (subidas que toleran errores de red si el archivo es gigante, como horas de grabación de obras de teatro).
- `credentials/`: *(Carpeta que debes crear)*. Acoge los proyectos exportados desde [Google Cloud Console](https://console.cloud.google.com).
- `scanned_videos.json`: Base de datos automática autogenerada por el escaner.

## Instalación y Preparación

### 1. PreRequisitos del Entorno (Python)
Abre PowerShell en esta carpeta y ejecuta:
```bash
pip install -r requirements.txt
```

### 2. Configurar la API de Google (Credenciales)
1. Con tu cuenta **escriturasperformaticascali@gmail.com**, ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea **2 o 3 Proyectos** nuevos (ej. "Youtube Uploader 1", "Youtube Uploader 2").
3. Dentro de cada proyecto:
   - Ve a "APIs & Services" > "Library" y busca/activa la **YouTube Data API v3**.
   - Ve a "APIs & Services" > "OAuth consent screen". Selecciona "External", dale un nombre y pon tu correo. En "Test Users", agrega tu mismo correo `escriturasperformaticascali@gmail.com`. *Esto es vital para que la app tenga permiso de subir a tu canal sin estar verificada por Google.*
   - Ve a "APIs & Services" > "Credentials". Haz clic en `+ CREATE CREDENTIALS` -> `OAuth client ID`.
   - Selecciona Application type: **Desktop app** (Aplicación de escritorio).
   - Descarga el archivo JSON de las credenciales de este proyecto.
4. Crea aquí una carpeta llamada `credentials`:
```bash
mkdir credentials
```
5. Mueve los archivos JSON descargados allí, y renómbralos como `client_secret_1.json`, `client_secret_2.json`, etc.

## Flujo de Trabajo (Uso real)

### 1. Escanear
Corre esto una sola vez por semana o mes para encontrar los nuevos recitales/eventos.
```bash
python video_scanner.py
```
> Encontrarás los resultados en `scanned_videos.json`. Puedes abrir este archivo para borrar entradas si no quieres subir un video específico antes de iniciar el uploader.

### 2. Subir
Ejecuta esto **una vez al día**:
```bash
python uploader.py
```
- ¿Qué pasa al hacerlo por primera vez? Se abrirá tu navegador para confirmar el acceso a la cuenta (verás una advertencia de "App no verificada", marca Continuar asumiendo el riesgo, es tu propia app de desarrollo que estás vinculando a tú mismo correo).
- **Subida y Programación Automática:** Los videos se subirán e inmediatamente se programarán mediante el campo `publishAt` oficial de YouTube para que salgan públicos a un ritmo estricto de **1 video por día** (a las 10:00 AM hora local aproximadamente). De esta manera, sin importar si el programa subió 15 hoy, se irán publicando espaciados en el calendario día tras día por los próximos 15 días.
- El script saltará entre las credenciales creadas (ej. client_secret_1 hasta client_secret_3) a medida que se agoten las cuotas, garantizando la subida en bloque de muchos videos a la vez.
