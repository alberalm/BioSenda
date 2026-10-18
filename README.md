# BioSenda

**BioSenda** es una aplicación web interactiva diseñada para enriquecer la experiencia de los senderistas en España, combinando información detallada de rutas con la biodiversidad observable a lo largo de cada recorrido. La plataforma presenta descripciones de flora y fauna adaptadas a un lenguaje divulgativo y comprensible, imágenes ilustrativas para facilitar su identificación en campo, un sistema de personalización de descripciones basado en Inteligencia Artificial generativa y la generación automática de guías de campo en PDF.

![Demostración de BioSenda](https://raw.githubusercontent.com/alberalm/Hackathon-PNAV/main/demo.gif)

---

## Contexto del proyecto y repositorio

El proyecto nació como propuesta para el reto *«Creación de itinerarios turísticos sostenibles con información sobre normativa y biodiversidad en la zona»*, en el marco del [Hackathon 2 del Programa Nacional de Algoritmos Verdes (PNAV)](https://algoritmosverdes.gob.es/es/hackathon/hackathon-energia-hidropredictiva).

> El repositorio entregado para el hackathon se encuentra disponible en **🔗[https://github.com/alberalm/Hackathon-PNAV](https://github.com/alberalm/Hackathon-PNAV)**, donde se pueden encontrar instrucciones para recrear la base de datos necesaria para la aplicación. Este repositorio (`BioSenda`) se centra exclusivamente en extraer, optimizar y evolucionar la aplicación web.

---

## Estructura del repositorio

```text
BioSenda/
├── app.py                     # Servidor backend (Flask + WsgiToAsgi para soporte asíncrono)
├── Dockerfile                 # Contenedor optimizado con Gunicorn + Uvicorn
├── requirements.txt           # Dependencias de Python
├── .env.example               # Plantilla de variables de entorno
├── connections/
│   ├── db_connection.py       # Conexión y pool SQLAlchemy (MySQL)
│   ├── llm_connection.py      # Conectores para LLMs (API o KoboldCpp)
│   └── README.md              # Documentación para configurar LLMs
├── scripts/
│   ├── pdf_maker.py           # Generador de folletos/guías PDF (fpdf2 + Pillow)
│   └── prompts.py             # Plantillas de prompts para Text2SQL y adaptación
├── static/                    # Archivos estáticos (logos, mapas base e iconos)
└── templates/
    └── main.html              # Frontend interactivo (HTML5, CSS y JavaScript)
```

---

## Guía de instalación y ejecución

Para ejecutar la aplicación es imprescindible disponer de una base de datos MySQL accesible con el esquema y tablas de BioSenda, configurada a través de la variable de entorno `DATABASE_URL` con formato:
```text
mysql+pymysql://<usuario>:<contraseña>@<host>:<puerto>/<nombre_bd>
```

A continuación se detallan las distintas formas de arrancar la aplicación:

### Opción 1: Ejecución local directa con Python

1. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
   > [Importante] Si tienes instalada previamente la librería obsoleta `fpdf`, desinstálala (`pip uninstall fpdf`) antes de instalar `fpdf2`.

2. **Configurar variables de entorno**:
   Copia el archivo `.env.example` como `.env` y define tu cadena de conexión:
   ```bash
   cp .env.example .env
   ```
   Edita `.env` con la URL de tu base de datos:
   ```env
   DATABASE_URL=mysql+pymysql://usuario:password@host:3306/biosenda
   ```

3. **Lanzar la aplicación**:
   ```bash
   python app.py
   ```
   Por defecto, el servidor se iniciará en `http://localhost:8080` (o en el puerto definido por la variable de entorno `PORT`).

---

### Opción 2: Ejecución local con Docker

Puedes empaquetar y ejecutar la aplicación dentro de un contenedor Docker pasando la variable `DATABASE_URL`:

1. **Construir la imagen**:
   ```bash
   docker buildx build -t biosenda .
   ```

2. **Ejecutar el contenedor**:
   - **Pasando la variable en la línea de comando**:
     ```bash
     docker run -d -p 8080:8080 -e DATABASE_URL="mysql+pymysql://usuario:password@host:3306/biosenda" --name biosenda biosenda
     ```
   - **O utilizando un archivo `.env`**:
     ```bash
     docker run -d -p 8080:8080 --env-file .env --name biosenda biosenda
     ```

   Accede a la aplicación en `http://localhost:8080`.

---

### Opción 3: Despliegue en Google Cloud Run

La aplicación está preparada para ejecutarse en entornos serverless basados en contenedores como **Google Cloud Run**.

Despliega el servicio directamente desde el código fuente pasando la variable `DATABASE_URL` a través del parámetro `--set-env-vars` o configurándolo como secreto o variable de entorno. Un ejemplo de comando es:

```bash
gcloud run deploy biosenda --region=europe-west1 --source=. --allow-unauthenticated \
  --set-env-vars DATABASE_URL="mysql+pymysql://usuario:password@host:3306/biosenda"
```

---

## Personalización de descripciones con LLMs (Opcional)

La personalización dinámica de las descripciones según peticiones libres del usuario requiere de un proveedor de modelos de lenguaje (Text2SQL + Generación). Esta funcionalidad es opcional; si no se configuran modelos, la aplicación seguirá funcionando mostrando las descripciones divulgativas predeterminadas.

Se admiten dos modalidades:
1. **Modelos locales mediante [KoboldCpp](https://github.com/LostRuins/koboldcpp):** Empleando las versiones cuantizadas en GGUF de los modelos Salamandra adaptados mediante fine-tuning y LoRA ([salamandra-7b-instruct-description-Q8_0-GGUF](https://huggingface.co/alberalm/salamandra-7b-instruct-description-Q8_0-GGUF) y [salamandra-7b-instruct-text2sql-Q8_0-GGUF](https://huggingface.co/alberalm/salamandra-7b-instruct-text2sql-Q8_0-GGUF)) o cualquier otro modelo general.
2. **APIs externas (OpenAI / Azure OpenAI / Google Gemini):** Configurando las credenciales y endpoints correspondientes en `connections/llm_connection.py` y `.env`.

Consulta la guía detallada de configuración en [connections/README.md](connections/README.md).

---

## Licencia y créditos

Este repositorio de la aplicación se distribuye bajo la licencia correspondiente al proyecto. Para más detalles sobre las licencias de los datos recopilados, modelos entrenados y cuadernos de análisis del hackathon original, consulta el repositorio matriz [Hackathon-PNAV](https://github.com/alberalm/Hackathon-PNAV).