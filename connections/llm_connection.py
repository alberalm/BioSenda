import os
import httpx


def personalizacion_habilitada() -> bool:
    """
    Comprueba si las variables de entorno necesarias para conectar con un LLM
    han sido configuradas (ya sea mediante API cloud o KoboldCpp local).
    """
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider == "api":
        return bool(os.getenv("LLM_BASE_URL") and os.getenv("LLM_API_KEY"))
    elif provider == "koboldcpp":
        return bool(os.getenv("KOBOLD_DESC_URL") or os.getenv("KOBOLD_SQL_URL"))
    return False


async def _mandar_mensaje_api(messages: list) -> str:
    """
    Plantilla para llamadas a APIs compatibles con chat/completions
    (Azure OpenAI, OpenAI, Google Gemini, etc.).
    """
    base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gpt-4.1")

    if "/chat/completions" in base_url:
        url = base_url
    else:
        url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


async def _mandar_mensaje_kobold(url: str, prompt: str, stop_sequence: str) -> str:
    """
    Plantilla para llamadas a instancias locales de KoboldCpp
    utilizando modelos cuantizados (formato GGUF).
    """
    endpoint = url if "/api/v1/generate" in url else f"{url.rstrip('/')}/api/v1/generate"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "prompt": prompt,
        "stop_sequence": [stop_sequence],
        "max_length": 350
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [{}])
        return results[0].get("text", "").strip() if results else ""


PREFIJO_PROMPT_DESCRIPCIONES = """
Eres un asistente que personaliza descripciones de especies para una aplicación de rutas.
El usuario ha proporcionado una petición, y tu objetivo es realizar los mínimos cambios necesarios a una descripción base para que se ajuste a la petición del usuario.
Recibirás cuatro bloques:

### Prompt:::

(Petición)

### Descripción a adaptar:::

(Descripción general de la especie.)

### Descripción científica:::

(Detalles científicos opcionales, a usar si son útiles para cumplir la petición.)

### Información adicional:::

(Contexto complementario en formato JSON.)

Instrucciones:

- Habla solamente en castellano salvo si el usuario pide lo contrario.
- Si la petición del usuario es relevante (por ejemplo: tono, nivel de detalle, enfoque en comportamiento, entorno, etc.), personaliza la descripción a adaptar con uno o dos enunciados breves, preferentemente al principio o final.
- Si el usuario pide algo no relacionado (por ejemplo: referencias a imágenes, gráficos o número de descripciones, peticiones fuera del alcance, etc.), deja la descripción exactamente igual.
- Repite exactamente la descripción a adaptar si decides no haces cambios. No expliques lo que haces.
- Devuelve solo el texto final adaptado, sin etiquetas ni bloques adicionales.
- **Si necesitas información que no te ha sido proporcionada, NO la inventes.** No hay nada de malo en devolver la descripción original si no dispones de la información necesaria.
- **Utiliza solamente la información proporcionada, a no ser que la petición del usuario implique la necesidad de ser creativo.**
"""

PREFIJO_PROMPT_TEXT2SQL = """
Tengo una aplicación cuyo objetivo es describir especies en el contexto de rutas, de forma que el usuario puede personalizar las descripciones.
El usuario ha proporcionado una petición, y tu objetivo es proporcionar una consulta para su base de datos SQL de forma que, dado un idtaxon/taxonid, ejecutándola se extraiga toda la información relevante para poder la petición.

La entrada tendrá el siguiente formato:

### Base de datos: (La estructura de la base de datos)
### Instrucción: (Petición)
### SQL: (Aquí deberá ir tu respuesta)

Instrucciones:

- Puedes asumir que tienes una descripción de la cual partir, un idtaxon/taxonid, el nombre aceptado de la especie y el nombre común preferente.
- Si necesitas usar el taxón de la especie (por ejemplo, si necesitas su taxonomía), utiliza <idtaxon>.
- Asegúrate de que la consulta SQL solo contiene las columnas e información relevante.
- Si el usuario te ha pedido algo que no es relevante para las descripciones o hace referencia a imágenes u algo que no te he mencionado, devuelve la consulta:
SELECT Null;
- Además, si el usuario pide "otras" provincias, rutas o clases, haz caso omiso de la palabra "otras", "otros" o similar.
- Razona primero qué tablas e información necesitas, y devuelve la consulta al final en el formato ```sql\n<consulta a realizar>\n```.
- No utilices ningún otro formato para la respuesta.
- La consulta debe estar completa a falta de posiblemente <idtaxon>, <nombre_aceptado> y <nombre_preferente>.

Ejemplos de consultas (observa que siempre se invluye el formato ```sql\n<consulta a realizar>\n```):

```sql
SELECT
    ne.nombre_comun
FROM
    NombresEspecies AS ne
WHERE
    ne.idtaxon = <idtaxon>
    AND ne.idioma = 'Inglés';
```

```sql
SELECT
    COUNT(DISTINCT r.ID_Ruta) AS NumeroDeRutas
FROM
    Taxonomia AS t
    INNER JOIN CuadriculasEspecies AS ce ON t.taxonid = ce.idtaxon
    INNER JOIN CuadriculasRutas AS cr ON ce.cuadricula = cr.CUADRICULA
    INNER JOIN Rutas AS r ON cr.ID_Ruta = r.ID_Ruta
WHERE
    t.taxonid = <idtaxon>;
```

```sql
SELECT
    t.class
FROM
    Taxonomia AS t
WHERE
    t.taxonid = <idtaxon>;
```
"""


async def send_description_prompt(prompt: str, i: int = 0) -> str:
    """
    Envía el prompt de adaptación de descripción al LLM configurado.
    """
    if not personalizacion_habilitada():
        raise RuntimeError("LLM no configurado. Define LLM_PROVIDER en las variables de entorno.")

    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider == "koboldcpp":
        url = os.getenv("KOBOLD_DESC_URL", "http://localhost:5001/api/v1/generate")
        return await _mandar_mensaje_kobold(url, prompt, '\n')
    else:
        messages = [
            {'role': 'system', 'content': PREFIJO_PROMPT_DESCRIPCIONES},
            {'role': 'user', 'content': prompt}
        ]
        r = await _mandar_mensaje_api(messages)
        return r.replace('\n\n', '\n').replace('\n', ' ').strip()


async def send_text2sql_prompt(prompt: str) -> str:
    """
    Envía el prompt de Text2SQL al LLM configurado y extrae la consulta SQL.
    """
    if not personalizacion_habilitada():
        raise RuntimeError("LLM no configurado. Define LLM_PROVIDER en las variables de entorno.")

    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider == "koboldcpp":
        url = os.getenv("KOBOLD_SQL_URL", "http://localhost:5002/api/v1/generate")
        res = await _mandar_mensaje_kobold(url, prompt, ';')
        return res.strip()
    else:
        messages = [
            {'role': 'system', 'content': PREFIJO_PROMPT_TEXT2SQL},
            {'role': 'user', 'content': prompt}
        ]
        r = await _mandar_mensaje_api(messages)
        if "```sql" in r:
            return r.split("```sql")[1].split("```")[0].strip()
        elif "```" in r:
            return r.split("```")[1].split("```")[0].strip()
        return r.strip()