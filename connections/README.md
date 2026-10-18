## Configuración del sistema de personalización de descripciones

Esta carpeta debería contener archivos que utiliza la aplicación para conectar con los modelos de lenguage. Es necesario crearlos antes de poder ejecutar con éxito la aplicación si se desea hacer uso de la personalización de descripciones.

### Conexión con modelos para descripciones y Text2SQL

---

Esta carpeta debería contener un archivo `llm_connection.py` que defina los métodos `async def send_description_prompt(prompt: str) -> str:` y `async def send_text2sql_prompt(prompt: str) -> str:`, que reciben una cadena de texto con el prompt completo y se la envían al modelo que se quiera utilizar. Por ejemplo, si se quieren utilizar los modelos entrenados, pueden usarse instancias de [KoboldCpp](https://github.com/LostRuins/koboldcpp) con las versiones cuantizadas de HuggingFace (véase la sección al final de esta guía):

```python
import requests

def send_prompt_kobold(url, prompt, stop_sequence):
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    data = {
        "prompt": prompt,
        "stop_sequence": [stop_sequence],
        "max_length": 350 # Suficiente para ambos casos de uso
    }

    response = requests.post(url, headers=headers, json=data)

    return response.json().get("results", [{}])[0].get("text", "")

def send_description_prompt(prompt: str) -> str:
    return send_prompt_kobold("http://localhost:5001/", prompt, '\n')

def send_text2sql_prompt(prompt: str) -> str:
    return send_prompt_kobold("http://localhost:5002/", prompt, ';')
```

Alternativamente, se puede utilizar un modelo de OpenAI, Google o Anthropic, entre otros. De ser este el caso, se recomienda modificar los prompts recibidos para que ofrezcan más detalles de instrucciones. Por ejemplo, para conectar con la API de Google Gemini, se puede utilizar el siguiente script:

```python
import google.generativeai as genai

genai.configure(api_key="<TU API KEY>)
model = genai.GenerativeModel('gemini-2.0-flash') # O cualquier otro modelo

PREFIJO_PROMPT_DESCRIPCIONES = """
Eres un asistente que personaliza descripciones de especies para una aplicación de rutas.
El usuario ha proporcionado una petición, y tu objetivo es realizar los mínimos cambios necesarios a una descripción base para que se ajuste a la petición del usuario.
Recibirás tres bloques:

### Prompt:::

(Petición del usuario.)

### Descripción a adaptar:::

(Descripción general de la especie.)

### Descripción científica:::

(Detalles científicos opcionales, a usar si son útiles para cumplir la petición.)

### Información adicional:::

(Contexto complementario en formato JSON.)

Instrucciones:

- Si la petición del usuario es relevante (por ejemplo: tono, nivel de detalle, enfoque en comportamiento, entorno, etc.), personaliza la descripción a adaptar con uno o dos enunciados breves, preferentemente al principio o final.
- Si el usuario pide algo no relacionado (por ejemplo: referencias a imágenes, gráficos o número de descripciones, peticiones fuera del alcance, etc.), deja la descripción exactamente igual.
- Repite exactamente la descripción a adaptar si decides no haces cambios. No expliques lo que haces.
- Devuelve solo el texto final adaptado, sin etiquetas ni bloques adicionales.

Aquí está la entrada:

"""

PREFIJO_PROMPT_TEXT2SQL = """
A continuación te incluiré la definición de mi base de datos en SQL.
Tengo una aplicación cuyo objetivo es describir especies en el contexto de rutas, de forma que el usuario puede personalizar las descripciones.
El usuario ha proporcionado una petición, y tu objetivo es proporcionar una consulta SQL de forma que, dado un idtaxon/taxonid, ejecutándola se extraiga toda la información relevante para poder la petición.

La entrada tendrá el siguiente formato:

### Base de datos: (La estructura de la base de datos)
### Instrucción: (Petición del usuario.)
### SQL: (Aquí deberá ir tu respuesta.)

Instrucciones:

- Puedes asumir que tienes una descripción de la cual partir, un idtaxon/taxonid, el nombre aceptado de la especie y el nombre común preferente.
- Si necesitas usar el taxón de la especie (por ejemplo, si necesitas su taxonomía), utiliza <idtaxon>.
- Asegúrate de que la consulta SQL solo contiene las columnas e información relevante.
- Si el usuario te ha pedido algo que no es relevante para las descripciones o hace referencia a imágenes u algo que no te he mencionado, devuelve la consulta:
SELECT Null
- Además, si el usuario pide "otras" provincias, rutas o clases, haz caso omiso de la palabra "otras", "otros" o similar.
- Razona primero qué tablas e información necesitas, y devuelve la consulta al final rodeada de ```sql ```.
- La consulta debe estar completa a falta de posiblemente <idtaxon>, <nombre_aceptado> y <nombre_preferente>.

Aquí está la entrada:

"""

def send_description_prompt(prompt: str) -> str:
    messages = [{'role': 'user', 'parts': [PREFIJO_PROMPT_DESCRIPCIONES + prompt]}]
    return  model.generate_content(messages).candidates[0].content.parts[0].text.strip()

def send_text2sql_prompt(prompt: str) -> str:
    messages = [{'role': 'user', 'parts': [PREFIJO_PROMPT_TEXT2SQL + prompt]}]
    return  model.generate_content(messages).candidates[0].content.parts[0].text.strip()
```


### Configuración de KoboldCpp

---

[KoboldCpp](https://github.com/LostRuins/koboldcpp) es un software creado sobre [LlamaCpp](https://github.com/ggml-org/llama.cpp) para cargar y utilizar de manera sencilla modelos en formato GGML y GGUF. Su elección para este proyecto se debe a la sencillez de configuración y diferentes utilidades que ofrece. Para utilizarlo con los modelos adaptados:

- Descarga la versión adecuada de KoboldCpp a través de su página de [releases](https://github.com/LostRuins/koboldcpp/releases).
- Descarga las versiones cuantizadas de los modelos de [descripciones](https://huggingface.co/alberalm/salamandra-7b-instruct-description-Q8_0-GGUF) y [Text2SQL](https://huggingface.co/alberalm/salamandra-7b-instruct-text2sql-Q8_0-GGUF).
- Ejecuta Kobold en los puertos 5001 y 5002 para los modelos de descripciones y Text2SQL, respectivamente. Esto se puede hacer con un comando similar a `koboldcpp.exe description_model.gguf --port 5001`. Opcionalmente, se pueden personalizar el número de hilos con `--threads`, forzar la carga en CPU con `--usecpu` y multitd de otros parámetros que se pueden analizar en la Wiki de KoboldCpp.
- Ejecutar la aplicación de manera normal y utilizar la personalización de descripciones.