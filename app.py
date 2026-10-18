from flask import Flask, render_template, send_file, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import random
import pandas as pd
import numpy as np
import io
from scripts.pdf_maker import PDF
import re
import json
import html
import unicodedata
import asyncio
import os
from scripts.prompts import TEXT2SQL_PROMPT, PERSONALIZE_DESCRIPTION_PROMPT
import signal
from asgiref.wsgi import WsgiToAsgi
import ipaddress
import sys
from dotenv import load_dotenv

load_dotenv()

from connections.db_connection import create_db_engine
from connections.llm_connection import send_description_prompt, send_text2sql_prompt, personalizacion_habilitada

engine = create_db_engine()

def handle_sigterm(signum, frame):
    flask_app.logger.info("SIGTERM received, shutting down.")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)

especies_cache = {}
flask_app = Flask(__name__)

# If behind a proxy (Cloud Run), trust X-Forwarded headers:
flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1)

def limpiar_texto(texto: str) -> str:
    if not texto:
        return ''
    # 1) NFC mantiene los caracteres compuestos (á, ñ, ü…)
    texto = unicodedata.normalize('NFC', texto)
    # 2) quita etiquetas HTML
    texto = re.sub(r'<[^>]+>', '', texto)
    # 3) convierte entidades (&aacute; → á)
    texto = html.unescape(texto)
    # 4) trim
    return texto.strip()


async def personalizar_especie(especie, descripcion_cientifica, query, prompt, i):
    null_str = """[\n  {\n    "": null\n  }\n]"""
    # Realizar la consulta
    try:
        if "select null" in query.lower():
            sql = null_str
        elif "<idtaxon>" in query:
            df_sql = pd.read_sql_query(query.replace("<idtaxon>", str(especie["idtaxon"])), engine)
            sql = json.dumps(df_sql.to_dict(orient='records'), indent=2)
        else:
            df_sql = pd.read_sql_query(query, engine)
            sql = json.dumps(df_sql.to_dict(orient='records'), indent=2)
    except Exception as e:
        print(f"Error parsing database output with idtaxon {especie['idtaxon']}: {e}")
        sql = null_str
    return await send_description_prompt(
        PERSONALIZE_DESCRIPTION_PROMPT.format(
            prompt=prompt,
            description_a_adaptar=especie["descripcion"],
            descripcion_cientifica=descripcion_cientifica,
            informacion_sql=sql
        ), i
    )


@flask_app.route('/')
def index():
    return render_template('main.html', personalizacion_habilitada=personalizacion_habilitada())


@flask_app.route('/personalizar_descripciones', methods=['POST'])
async def personalizar_descripciones():
    if not personalizacion_habilitada():
        return jsonify({'error': 'La personalización de descaripciones no está configurada.'}), 400

    data = request.get_json(force=True) or {}
    prompt = data.get('prompt', '')
    especies  = data.get('especies', [])

    # Obtener la consulta SQL que complementa el prompt del usuario
    text2sql_query = await send_text2sql_prompt(TEXT2SQL_PROMPT.format(prompt=prompt))
    # Cambiar la consulta para que solamente coja 30 filas
    if text2sql_query.strip().endswith(';'):
        text2sql_query = text2sql_query.replace(';', '\nLIMIT 30;')
    else:
        text2sql_query = text2sql_query.strip() + '\nLIMIT 30;'
    print(f"Query generada:\n{text2sql_query}")
    # Construir el union_sql con los idtaxones
    union_sql = " UNION ALL ".join([f"SELECT {especie['idtaxon']} AS idtaxon" for especie in especies])
    # Hacer queries a la base de datos
    scientific_descriptions_query = f"""
    SELECT
        d.idtaxon,
        Descripcion AS descripcion
    FROM
        DescripcionesEspecies d
    JOIN (
        {union_sql}
    ) AS w
        ON d.idtaxon = w.idtaxon
    """
    sql_result = pd.read_sql_query(scientific_descriptions_query, engine)
    descriptions = dict(zip(sql_result['idtaxon'], sql_result['descripcion']))
    tasks = {
        especie["idtaxon"]: personalizar_especie(especie, descriptions[especie["idtaxon"]], text2sql_query, prompt, i)
        for i, especie in enumerate(especies)
    }
    # Hacer un await de todas las corrutinas
    results = await asyncio.gather(*tasks.values())
    # Asociar de nuevo los idtaxones
    new_descs = dict(zip(tasks.keys(), results))
    for i in range(len(especies)):
        especies[i]["descripcion"] = new_descs[especies[i]["idtaxon"]].strip()
    
    return jsonify(especies)


@flask_app.route('/obtener_especies', methods=['POST'])
def obtener_especies():
    data = request.get_json(force=True) or {}
    try:
        id_ruta = int(data.get('id_ruta', 1))
    except Exception:
        id_ruta = 1
    
    client_ip = request.remote_addr or '0.0.0.0'

    all_groups = [
        "peces","mamiferos","hongos","plantas_vasculares",
        "plantas_no_vasculares","aves","anfibios","invertebrados","reptiles"
    ]
    quotas = {
        0:(3,3), 1:(12,2), 2:(7,2), 3:(5,2),
        4:(5,2), 5:(4,2), 6:(4,1), 7:(3,2),
        8:(3,1), 9:(3,1)
    }
    raw_filters = data.get('taxonomias', [])
    sel = [g for g in all_groups if g in map(str.lower, raw_filters)]
    k = len(sel)
    cuota_sel, cuota_rest = quotas.get(k, quotas[0])

    sql_counts = """
        SELECT
            ce.idtaxon,
            LOWER(t.taxonomicgroup)         AS grupo,
            COUNT(DISTINCT(ce.cuadricula))  AS ocurrencias,
            COUNT(DISTINCT(i.photo_link))   AS imagenes
        FROM CuadriculasRutas cr
        JOIN CuadriculasEspecies ce
            ON cr.CUADRICULA = ce.cuadricula
        JOIN Taxonomia t
            ON ce.idtaxon = t.taxonid
            AND t.nametype = 'Aceptado'
        LEFT JOIN Imagenes i
            ON i.taxonid = ce.idtaxon
        WHERE cr.ID_Ruta = {id_ruta}
        GROUP BY ce.idtaxon, LOWER(t.taxonomicgroup)
    """
    print(f"Cogiendo contador de especies para la ruta con id {id_ruta}")
    df_counts = pd.read_sql_query(sql_counts.format(id_ruta=id_ruta), engine)

    dfs = []
    for group in set(df_counts['grupo']):
        group_count = cuota_sel if group in sel else cuota_rest
        group_df = df_counts[df_counts['grupo'] == group].copy()
        group_df['imagenes'] = group_df['imagenes'].astype(int)
        group_df_images = group_df[group_df['imagenes'] > 0]
        if len(group_df_images) > 0:
            n_images = min(len(group_df_images), group_count)
            try:
                seed = n_images + int(ipaddress.ip_address(client_ip))
            except Exception:
                seed = n_images
            dfs.append(group_df_images.sample(
                n=n_images,
                random_state=seed,
                weights=group_df_images['ocurrencias'].tolist()
            ))
            remaining = group_count - n_images
            if remaining > 0:
                group_df_no_images = group_df[group_df['imagenes'] == 0]
                if len(group_df_no_images) > 0:
                    try:
                        seed = remaining + int(ipaddress.ip_address(client_ip))
                    except Exception:
                        seed = remaining
                    dfs.append(group_df_no_images.sample(
                        n=min(len(group_df_no_images), remaining),
                        random_state=seed,
                        weights=group_df_no_images['ocurrencias'].tolist()
                    ))
    try:
        rng = random.Random(id_ruta + int(ipaddress.ip_address(client_ip)))
    except Exception:
        rng = random.Random(id_ruta)
    joined_df = pd.concat(dfs)
    selected_ids = joined_df['idtaxon']
    selected_images = joined_df['imagenes'].apply(lambda x: rng.randint(0, x-1) if x > 1 else 0)
    desc_numbers = [rng.randint(1, 3) for _ in selected_ids]

    # Construir el union_sql con los pares (idtaxon, descripcion)
    union_sql = " UNION ALL ".join([
        f"SELECT {idtaxon} AS idtaxon, {desc_num} AS num_desc, {image_num} as image"
        for (idtaxon, desc_num, image_num) in zip(selected_ids, desc_numbers, selected_images)
    ])

    sql_details = f"""
        WITH numbered_images AS (
        SELECT
            taxonid,
            photo_link,
            license_holder,
            ROW_NUMBER() OVER (
            PARTITION BY taxonid
            ORDER BY photo_link
            ) AS rn
        FROM Imagenes
        )
        SELECT
            de.idtaxon,
            t.taxonomicgroup    AS grupo,
            ne.nombre_comun            AS nombre_comun,
            t.name                     AS nombre_cientifico,
            CASE w.num_desc
                WHEN 1 THEN de.Gemini1
                WHEN 2 THEN de.Gemini2
                WHEN 3 THEN de.Gemini3
            END                         AS descripcion,
            t.isinvasive,
            t.conservationstatus,
            ni.photo_link,
            ni.license_holder
        FROM DescripcionesEspecies de
        JOIN (
            {union_sql}
        ) AS w
            ON de.idtaxon = w.idtaxon

        JOIN Taxonomia t
            ON de.idtaxon = t.taxonid
            AND t.nametype = 'Aceptado'

        LEFT JOIN NombresEspecies ne
            ON de.idtaxon   = ne.idtaxon
            AND ne.idioma    = 'Castellano'
            AND ne.espreferente = 1

        -- pick the Nth image (0-based image = 1-based rn)
        LEFT JOIN numbered_images ni
            ON ni.taxonid = w.idtaxon
            AND ni.rn      = w.image + 1;
    """

    df_details = pd.read_sql_query(sql_details.format(union_sql=union_sql), engine)
    
    df_details = df_details.replace({np.nan: None})
    especies = df_details.to_dict(orient='records')

    return jsonify(especies)


@flask_app.route('/generar_pdf', methods=['POST'])
async def generar_pdf():
    """
    Funcion que se encarga de generar el PDF a partir de la ruta seleccionada
    """
    data      = request.get_json(force=True)
    id_ruta   = limpiar_texto(data.get('id_ruta', '0'))
    nombre    = limpiar_texto(data.get('nombre', '-'))
    etapa     = limpiar_texto(data.get('etapa',  '-'))
    longitud  = limpiar_texto(data.get('longitud', '-'))
    provincia = limpiar_texto(data.get('provincia', '-'))
    ccaa      = limpiar_texto(data.get('ccaa', '-'))
    especies  = data.get('especies', [])
    
    pdf = PDF()
    
    pdf.initialise(
        especies,
        nombre_ruta   = nombre,
        nombre_etapa  = etapa,
        longitud      = longitud,
        provincia     = provincia,
        ccaa          = ccaa,
        id_ruta       = id_ruta
    )

    await pdf.create_pdf()
    pdf_bytes = bytes(pdf.output())
    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=False)


@flask_app.route('/obtener_rutas', methods=['GET'])
def obtener_rutas():
    """
    Obtiene todas las rutas de la base de datos y filtra por provincia si se proporciona
    """
    provincia = request.args.get('provincia', default='', type=str).strip()

    try:
        # 1) Lee TODAS las rutas
        df_rutas = pd.read_sql_query(
            "SELECT ID_Ruta, Nombre_Ruta, Nombre_Etapa, ROUND(Longitud, 2) AS Longitud, CCAA, Provincia FROM Rutas",
            engine
        )
        # 2) Normaliza NaN a None para el JSON
        df_rutas = df_rutas.replace({np.nan: "-"})

        # 3) Si hay filtro de provincia, aplica contains (caso insensible)
        if provincia:
            # Elimina espacios a ambos lados y busca substring
            df_rutas = df_rutas[
                df_rutas['Provincia']
                  .fillna('')
                  .str
                  .contains(provincia, case=False, na=False)
            ]

        rutas = df_rutas.to_dict(orient='records')
        return jsonify(rutas)

    except Exception as e:
        flask_app.logger.exception("Error en obtener_rutas:")
        return jsonify({'error': str(e)}), 500


# Convertir la aplicacion de Flask en asincrona para que soporte llamadas concurrentes
app = WsgiToAsgi(flask_app)

# Para local, se usa la aplicacion de Flask
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)