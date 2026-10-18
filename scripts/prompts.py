
TEXT2SQL_PROMPT = """
### Base de datos:

CREATE TABLE `Taxonomia` ( -- Tabla que define las especies (taxones)
    `taxonid` INT NOT NULL, -- Identificador
    `name` VARCHAR(200), -- Nombre científico
    `taxonrank` VARCHAR(15), -- Rango del taxón, puede ser: "Species", "Subspecies", "Variety", "Form"
    `origen` VARCHAR(50), -- Si es especie nativa o no
    `taxonomicgroup` VARCHAR(50), -- El grupo taxonómico
    `kingdom` VARCHAR(50), -- El reino taxonómico
    `phylum` VARCHAR(50), -- El philo taxonómico
    `class` VARCHAR(50), -- La clase taxonómico
    `taxonorder` VARCHAR(50), -- El orden taxonómico
    `family` VARCHAR(50), -- La familia taxonómica
    `genus` VARCHAR(50), -- El género taxonómico
    `subgenus` VARCHAR(50), -- El subgénero taxonómico
    `nametype` VARCHAR(50), -- Tipo de nombre, puede ser "Aceptado" o "Sinónimo"
);

CREATE TABLE `Cuadriculas` ( -- Tabla que define las cuadrículas
    `CUADRICULA` CHAR(7) NOT NULL, -- Codigo de la cuadrícula
    `CCAA` VARCHAR(50), -- Comunidad autonoma a la que pertenece la cuadrícula
    `Provincia` VARCHAR(50) -- Provincia a la que pertenece la cuadrícula
);

CREATE TABLE `Rutas` ( -- Tabla que define las rutas
    `ID_Ruta` INT NOT NULL, -- Identificador
    `Nombre_Ruta` TEXT NOT NULL, -- El nombre de la ruta
    `Nombre_Etapa` TEXT, -- El nombre de la etapa, si existe
    `Longitud` FLOAT, -- La longitud de la etapa/ruta
    `CCAA` TEXT, -- La Comunidad Autónoma a la que pertenece la etapa/ruta
    `Provincia` TEXT -- La provincia a la que pertenece la etapa/ruta
);

CREATE TABLE `CuadriculasEspecies` ( -- Tabla que relaciona las especies con las cuadrículas
    `idtaxon` INT NOT NULL,
    `cuadricula` CHAR(7) NOT NULL
);

CREATE TABLE `CuadriculasRutas` ( -- Tabla que relaciona las rutas con las cuadrículas
    `ID_Ruta` INT NOT NULL,
    `CUADRICULA` CHAR(7) NOT NULL
);

CREATE TABLE `NombresEspecies` ( -- Tabla de nombres para cada taxón
    `idtaxon` INT NOT NULL, -- Identificador
    `nombre_comun` VARCHAR(50) NOT NULL, -- Nombre comun para el taxón
    `idioma` VARCHAR(50), -- Idioma del nombre comun, el español aparece como "Castellano"
    `espreferente` FLOAT -- Si es el nombre común preferente o no, toma valores 1 o 0
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