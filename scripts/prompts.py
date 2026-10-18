
TEXT2SQL_PROMPT = """
### Base de datos:
CREATE TABLE [dbo].[Taxonomia]( -- Tabla que define las especies (taxones)
    [taxonid] [int] NOT NULL, -- Identificador
    [name] [varchar(MAX)] NULL, -- Nombre científico
    [taxonrank] [varchar(MAX)] NULL, -- Rango del taxón, puede ser: "Species", "Subspecies", "Variety", "Form"
    [origen] [varchar(MAX)] NULL, -- Si es especie nativa o no
    [taxonomicgroup] [varchar(MAX)] NULL, -- El grupo taxonómico
    [kingdom] [varchar(MAX)] NULL, -- El reino taxonómico
    [phylum] [varchar(MAX)] NULL, -- El philo taxonómico
    [class] [varchar(MAX)] NULL, -- La clase taxonómico
    [taxonorder] [varchar(MAX)] NULL, -- El orden taxonómico
    [family] [varchar(MAX)] NULL, -- La familia taxonómica
    [genus] [varchar(MAX)] NULL, -- El género taxonómico
    [subgenus] [varchar(MAX)] NULL, -- El subgénero taxonómico
    [nametype] [varchar(MAX)] NULL -- Tipo de nombre, puede ser "Aceptado" o "Sinónimo"
)

CREATE TABLE [dbo].[NombresEspecies]( -- Tabla de nombres para cada taxón
    [idtaxon] [int] NULL, -- Identificador
    [nombre_comun] [varchar(MAX)] NULL, -- Nombre comun para el taxón
    [idioma] [varchar(MAX)] NULL, -- Idioma del nombre comun, el español aparece como "Castellano"
    [espreferente] [int] NULL -- Si es el nombre común preferente o no, toma valores 1 o 0
)

CREATE TABLE [dbo].[Rutas](-- Tabla que define las rutas
    [ID_Ruta] [int] NOT NULL, -- Identificador
    [Nombre_Ruta] [varchar(MAX)] NULL, -- El nombre de la ruta
    [Nombre_Etapa] [varchar(MAX)] NULL, -- El nombre de la etapa, si existe
    [Longitud] [float] NULL, -- La longitud de la etapa/ruta
    [CCAA] [varchar(MAX)] NULL, -- La Comunidad Autónoma a la que pertenece la etapa/ruta
    [Provincia] [varchar(MAX)] NULL, -- La provincia a la que pertenece la etapa/ruta
)

CREATE TABLE [dbo].[Cuadriculas]( -- Tabla que define las cuadrículas
    [CUADRICULA] [nchar](7) NOT NULL, -- Codigo de la cuadrícula
    [CCAA] [varchar(MAX)] NULL, -- Comunidad autonoma a la que pertenece la cuadrícula
    [Provincia] [varchar(MAX)] NULL -- Provincia a la que pertenece la cuadrícula
)

CREATE TABLE [dbo].[CuadriculasEspecies]( -- Tabla que relaciona las especies con las cuadrículas
    [idtaxon] [int] NOT NULL, 
    [cuadricula] [nchar](7) NOT NULL
)

CREATE TABLE [dbo].[CuadriculasRutas]( -- Tabla que relaciona las rutas con las cuadrículas
    [ID_Ruta] [int] NULL,
    [CUADRICULA] [nchar](7) NULL
)
### Instrucción: {prompt}
### SQL:
""".strip()


PERSONALIZE_DESCRIPTION_PROMPT = """
### Prompt:::

{prompt}

### Descripcion a adaptar:::

{description_a_adaptar}

### Descripción científica:::

{descripcion_cientifica}

### Información adicional:::

{informacion_sql}

### Nueva descripción:::

"""