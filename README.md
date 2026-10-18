
Esta carpeta contiene los programas de backend y frontend necesarios para ejecutar y mostrar la página web junto con sus funcionalidades. Entre ellos encontramos:

- Un archivo en formato .py que hace uso del framework flask (`app.py`).
- El archivo HTML que detalla la interfaz (`main.html`).
- La carpeta de imágenes locales (`static`).
- Un generador de PDFs para cada ruta (`pdf_maker.py`).

---

- **app.py**  

  Código fuente del backend de la aplicación. Contiene la lógica para arrancar un servidor flask y atender las siguientes peticiones del frontend:

  - `GET /obtener_rutas` – Devuelve la lista de rutas disponibles y las pasa a `main.html`.  
  - `POST /obtener_especies` – Devuelve las especies asociadas a la ruta seleccionada, realizando previamente consultas a la base de datos SQL para obtener la especie más común en las cuadrículas por las que discurre la ruta.  
  - `POST /personalizar_descripciones` – Captura el prompt de personalización introducido por el usuario y hace uso de LLMs para generar descripciones adaptadas 
  - `POST /generar_pdf` – Genera el PDF que muestra las especies filtradas, agrupadas por categoría taxonómica, con sus descripciones e información básica (nombres, estado de conservación, etcetera).

- **pdf_maker.py**  

  Módulo en `scripts` que genera la estructura básica del PDF al elegir una ruta, utilizando la librería `fpdf2`. También emplea `pillow` para cargar las imágenes de las especies e incorporarlas al documento.

- **prompts.py**  

  Plantillas de prompt para el LLM:  
  - `TEXT2SQL_PROMPT` – Convierte texto libre en una consulta SQL.  
  - `PERSONALIZE_DESCRIPTION_PROMPT` – Adapta descripciones científicas al estilo indicado.

  Las imágenes de rutas y especies se descargan de forma asíncrona y concurrente con `asyncio`. En particular, las de rutas se obtienen de [este repositorio público](https://huggingface.co/datasets/alberalm/hiking-trails-images-spain).

- **main.html**  

  Interfaz del frontend: el archivo HTML que carga la parte visual de la página web y gestiona botones y filtros.  
  - **Primera parte:**: CSS de la página.  
  - **Segunda parte:**: Estructura HTML (botones, tabla, área de texto, imágenes, etcetera).  
  - **Tercera parte:**: Codigo javaScript para conectar con el backend (`app.py`) y manejar las interacciones.

- **static**  

  Carpeta con imágenes e iconos estáticos de la aplicación, de acceso directo para la interfaz.

---

## Guía de uso

Correr la aplicación de BioSenda en local requiere de múltiples prerrequisitos:

- Instalación de las librerías necesarias (véase `requirements.txt`). Conviene desinstalar la librería `fpdf` antes de instalar `fpdf2`, ya que pueden dar errores si se instalan ambas.
- Alojamiento de la base de datos que se encuentra en `2. Base de datos` en un servidor o equivalente.
- Crear .env a partir de .env.example. Se debe añadir la URL de conexión a la base de datos en este archivo.
- (Opcional) creación de los scripts para realizar llamadas a LLM. Esto se utiliza exclusivamente para la personalización de las descripciones y no es necesario para un uso básico de la aplicación. Más detalles para la configuración de esta funcionaliadad están disponibles en `connections/README.md`.

Una vez cumplido todo lo anterior, simplemente se debe ejecutar el archivo `app.py` y acceder al servidor en `localhost` correspondiente. Se anima a explorar la página y descubrir sus funcionalidades .


# Para correr la app:

docker buildx build -t biosenda .

docker run -p 8080:8080 --name biosenda biosenda

gcloud run deploy biosenda --region=europe-west1 --source=. --allow-unauthenticated