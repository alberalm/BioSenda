from flask import Flask, render_template, send_file, request, jsonify
import random
import unicodedata
import pandas as pd
from sqlalchemy import create_engine
import numpy as np
import io
from scripts.pdf_maker import PDF
import re
import json
import html
import unicodedata
import asyncio
try:
    from connections.llm_connection import send_description_prompt, send_text2sql_prompt
except:
    print("No models defined, personalising descriptions is not available and will not work.")
from scripts.prompts import TEXT2SQL_PROMPT, PERSONALIZE_DESCRIPTION_PROMPT


especies_cache = {}
app = Flask(__name__)
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=tcp:sql-server-mamba.database.windows.net,1433;"
    "DATABASE=sql-db-mamba;"
    "UID=sql-admin;"
    "PWD=serverpwd1!;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={conn_str}")


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


def personalizar_especie(especie, descripcion_cientifica, query, prompt):
    null_str = """[\n  {\n    "": null\n  }\n]"""
    # Realizar la consulta
    try:
        if "SELECT NULL" in query.lower():
            sql = null_str
        elif "<idtaxon>" in query:
            df_sql = pd.read_sql_query(query.replace("<idtaxon>", especie["idtaxon"]))
            sql = json.dumps(df_sql.to_dict(orient='records'), indent=2)
        else:
            df_sql = pd.read_sql_query(query)
            sql = json.dumps(df_sql.to_dict(orient='records'), indent=2)
    except Exception:
        sql = null_str
    return  send_description_prompt(
        PERSONALIZE_DESCRIPTION_PROMPT.format(
            prompt=prompt,
            description_a_adaptar=especie["descripcion"],
            descripcion_cientifica=descripcion_cientifica,
            informacion_sql=sql
        )
    )
    


@app.route('/')
def index():
    return render_template('principal.html.html')


@app.route('/personalizar_descripciones', methods=['POST'])
def personalizar_descripciones():
    data = request.get_json(force=True) or {}
    prompt = data.get('prompt', '')
    especies  = data.get('especies', [])

    # Obtener la consulta SQL que complementa el prompt del usuario
    text2sql_query = send_text2sql_prompt(TEXT2SQL_PROMPT.format(prompt=prompt))
    # Cambiar la consulta para que solamente coja 30 filas
    if 'SELECT DISTINCT' in text2sql_query:  # TOP debe ir despues de DISTINCT
        text2sql_query = text2sql_query.replace('SELECT DISTINCT', 'SELECT DISTINCT TOP 30')
    else:
        text2sql_query = text2sql_query.replace('SELECT', 'SELECT TOP 30')
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
    new_descs = {
        especie["idtaxon"]: personalizar_especie(especie, descriptions[especie["idtaxon"]], text2sql_query, prompt ) for especie in especies
    }
    for i in range(len(especies)):
        especies[i]["descripcion"] = new_descs[especies[i]["idtaxon"]].strip()
    
    return jsonify(especies)


@app.route('/obtener_especies', methods=['POST'])
def obtener_especies():
    data = request.get_json(force=True) or {}
    try:
        id_ruta = int(data.get('id_ruta', 1))
    except:
        id_ruta = 1
    
    client_ip = request.remote_addr or '0.0.0.0'

    ALL_GROUPS = [
        "peces","mamiferos","hongos","plantas_vasculares",
        "plantas_no_vasculares","aves","anfibios","invertebrados","reptiles"
    ]
    QUOTAS = {
        0:(3,3), 1:(12,2), 2:(7,2), 3:(5,2),
        4:(4,2), 5:(4,2), 6:(4,1), 7:(3,2),
        8:(3,1), 9:(3,1)
    }
    raw_filters = data.get('taxonomias', [])
    sel = [g for g in ALL_GROUPS if g in map(str.lower, raw_filters)]
    k = len(sel)
    cuota_sel, cuota_rest = QUOTAS.get(k, QUOTAS[0])

    sql_counts = """
        SELECT
            ce.idtaxon,
            LOWER(t.taxonomicgroup)         AS grupo,
            COUNT(DISTINCT(ce.cuadricula))  AS ocurrencias,
            COUNT(DISTINCT(i.photo_link))   AS imagenes
        FROM dbo.CuadriculasRutas cr
        JOIN dbo.CuadriculasEspecies ce
            ON cr.CUADRICULA = ce.cuadricula
        JOIN dbo.Taxonomia t
            ON ce.idtaxon = t.taxonid
            AND t.nametype = 'Aceptado'
        LEFT JOIN dbo.Imagenes i
            ON i.taxonid = ce.idtaxon
        WHERE cr.ID_Ruta = {id_ruta}
        GROUP BY ce.idtaxon, LOWER(t.taxonomicgroup)
    """
    print(f"Cogiendo contador de especies para la ruta con id {id_ruta}")
    df_counts = pd.read_sql_query(sql_counts.format(id_ruta=id_ruta), engine)

    dfs = []
    for group in set(df_counts['grupo']):
        group_count = cuota_sel if group in sel else cuota_rest
        group_df = df_counts[df_counts['grupo'] == group]
        group_df_images = group_df[group_df['imagenes'] > 0]
        if len(group_df_images) > 0:
            n_images = min(len(group_df_images), group_count)
            try:
                seed = n_images + sum(int(octet) << (8 * i) for i, octet in enumerate(reversed(client_ip.split('.'))))
            except:
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
                        seed = remaining + sum(int(octet) << (8 * i) for i, octet in enumerate(reversed(client_ip.split('.'))))
                    except:
                        seed = remaining
                    dfs.append(group_df_no_images.sample(
                        n=min(len(group_df_no_images), remaining),
                        random_state=seed,
                        weights=group_df_no_images['ocurrencias'].tolist()
                    ))

    rng = random.Random(id_ruta + sum(int(octet) << (8 * i) for i, octet in enumerate(reversed(client_ip.split('.')))))
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
        FROM dbo.Imagenes
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
        FROM dbo.DescripcionesEspecies de
        JOIN (
            {union_sql}
        ) AS w
            ON de.idtaxon = w.idtaxon

        JOIN dbo.Taxonomia t
            ON de.idtaxon = t.taxonid
            AND t.nametype = 'Aceptado'

        LEFT JOIN dbo.NombresEspecies ne
            ON de.idtaxon   = ne.idtaxon
            AND ne.idioma    = 'Castellano'
            AND ne.espreferente = 1

        -- pick the Nth image (0-based image = 1-based rn)
        LEFT JOIN numbered_images ni
            ON ni.taxonid = w.idtaxon
            AND ni.rn      = w.image + 1;
    """

    df_details = pd.read_sql_query(sql_details.format(union_sql=union_sql), engine)
    
    df_details = (
        df_details.replace({np.nan: None})
    )
    especies = df_details.to_dict(orient='records')

    return jsonify(especies)


@app.route('/generar_pdf', methods=['POST'])
def generar_pdf():
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

    asyncio.run(pdf.create_pdf())
    pdf_bytes = bytes(pdf.output())
    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=False)


@app.route('/obtener_rutas', methods=['GET'])
def obtener_rutas():
    """
    Obtiene todas las rutas de la base de datos y filtra por provincia si se proporciona
    """
    provincia = request.args.get('provincia', default='', type=str).strip()

    try:
        # 1) Lee TODAS las rutas
        df_rutas = pd.read_sql(
            "SELECT ID_Ruta, Nombre_Ruta, Nombre_Etapa, ROUND(Longitud, 2) AS Longitud, CCAA, Provincia FROM Rutas",
            con=engine
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
        app.logger.exception("Error en obtener_rutas:")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
