from fpdf import FPDF
import httpx
from PIL import Image
from io import BytesIO
from collections import defaultdict
from fpdf.enums import XPos, YPos
import asyncio


class PDF(FPDF):

    def initialise(self, especies, nombre_ruta, nombre_etapa, longitud, provincia, ccaa, id_ruta):
        # Mapa de colores
        self.color_map = {
            "EX (Extinto)": (0, 0, 0),
            "EW (Extinto en estado silvestre)": (90, 0, 74),
            "RE (Extinto regionalmente)": (165, 90, 156),
            "CR (En peligro crítico)": (239, 0, 41),
            "EN (En peligro)": (255, 165, 82),
            "VU (Vulnerable)": (255, 247, 0),
            "NT (Casi amenazado)": (151, 193, 21),
            "LC (Preocupación menor)": (123, 189, 82),
            "DD (Datos insuficientes)": (195, 195, 195),
            "NE (No evaluado)": (229, 229, 229),
            # cualquier otro o None → blanco
        }
        # Descargar las imagenes lo primero, que es lo que mas tarda
        self.imagen_ruta_task = self.obtener_imagen(
            f"https://huggingface.co/datasets/alberalm/hiking-trails-images-spain/resolve/main/{id_ruta}.png?download=true",
            recortar=self.recortar_bordes
        )
        self.imagenes_tasks = [self.obtener_imagen(especie["photo_link"], self.recortar_a_cuadrado) for especie in especies]
        self.taxones = [e["idtaxon"] for e in especies]
        especies_por_grupo = defaultdict(list)
        for especie in especies:
            grupo = especie["grupo"]
            especies_por_grupo[grupo].append(especie)
        self.especies_por_grupo = especies_por_grupo
        self.nombre_ruta = nombre_ruta
        self.nombre_etapa = nombre_etapa
        self.longitud = longitud
        self.provincia = provincia
        self.ccaa = ccaa

    def recortar_a_cuadrado(self, imagen):
        ancho, alto = imagen.size
        lado = min(ancho, alto)
        izquierda = (ancho - lado) // 2
        arriba = (alto - lado) // 2
        derecha = izquierda + lado
        abajo = arriba + lado
        return imagen.crop((izquierda, arriba, derecha, abajo))
    

    def recortar_bordes(self, imagen, margen=20):
        ancho, alto = imagen.size
        izquierda = margen
        arriba = 5*margen
        derecha = ancho - margen
        abajo = alto - margen
        return imagen.crop((izquierda, arriba, derecha, abajo))
    

    async def obtener_imagen(self, url_imagen, recortar):
        if url_imagen is None:
            return None
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url_imagen)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
                img = recortar(img)
                return img
        except Exception as e:
            return None


    def footer(self):
        self.set_y(-20)

        # ---- Marca BioSenda ----
        icon_size = 12
        espacio = 2
        text = "BioSenda"
        self.set_font("Helvetica", "", 10)
        text_width = self.get_string_width(text)

        # Calcula el punto x de inicio (pegado al margen derecho)
        x_icon = self.w - self.r_margin - icon_size - espacio - text_width - 2
        y_icon = self.get_y()

        # Centrado vertical preciso del texto respecto al logo
        y_text = y_icon + (icon_size - 2.8) / 3 + 0.5
        self.set_xy(x_icon + icon_size + espacio, y_text)
        self.cell(text_width, 5, text)
        
        # Logo
        try:
            self.image("static/logo.png", x=x_icon, y=y_icon, w=icon_size, dims=(100,100))
        except Exception as e:
            print(f"Error cargando logo: {e}")

        # ---------- Número de página centrado ----------
        self.set_font("Helvetica", "", 10)
        page_text = f"Página {self.page_no()} de {{nb}}"
        page_width = self.get_string_width(page_text)
        self.set_x((self.w - page_width) / 2)
        self.cell(page_width, 10, page_text)


    def fit_text(self, text, max_width, font_name="Helvetica", style="B", 
             max_size=20, min_size=6, step=0.5):
        """
        Ajusta el tamaño de fuente para que `text` quepa en `max_width`.
        - max_size: tamaño inicial (arranca grande)
        - min_size: tamaño mínimo que queremos permitir
        - step: decremento en cada iteración
        """
        size = max_size
        self.set_font(font_name, style, size)
        # Mientras no quepa y no hayamos llegado al mínimo
        while size > min_size and self.get_string_width(text) > max_width:
            size -= step
            self.set_font(font_name, style, size)
        return size


    def add_portada(self, imagen_ruta):
        # ---- Medidas del bloque flotante
        x_ini = 0
        y_ini = 10
        ancho = 170
        alto = 40
        dobladillo = 25  # el pico lateral

        # ---- Sombra debajo
        self.set_fill_color(130, 181, 150)
        self.polygon([
            (x_ini, y_ini),
            (x_ini + ancho + 2, y_ini + 2),
            (x_ini + ancho + dobladillo + 2, y_ini + alto // 2 + 2),
            (x_ini + ancho + 2, y_ini + alto + 2),
            (x_ini, y_ini + alto + 2)
        ], style="F")

        # ---- Banner principal
        self.set_fill_color(160, 211, 180)
        self.polygon([
            (x_ini, y_ini),
            (x_ini + ancho, y_ini),
            (x_ini + ancho + dobladillo, y_ini + alto // 2),
            (x_ini + ancho, y_ini + alto),
            (x_ini, y_ini + alto)
        ], style="F")

        # ---- Texto dentro del banner
        self.set_text_color(0)

        # Cálculo del centro del banner
        center_x = (self.w - self.l_margin - self.r_margin) / 2 + self.l_margin
        center_y = y_ini + alto / 2

        # Título
        # Cálculo del centro del banner
        center_x = (self.w - self.l_margin - self.r_margin) / 2 + self.l_margin
        center_y = y_ini + alto / 2

        # Determinamos el ancho máximo para el título
        max_title_width = ancho - 10  # el ancho del banner

        # Encuentra el tamaño de fuente óptimo
        opt_size = self.fit_text(self.nombre_ruta, max_title_width, 
                                font_name="Helvetica", style="B", max_size=20, min_size=8)

        # Recoloca y dibuja el título
        titulo_width = self.get_string_width(self.nombre_ruta)
        self.set_xy(center_x - titulo_width / 2, center_y - 10)
        self.cell(titulo_width, opt_size, self.nombre_ruta, align='C')

        # Subtítulo debajo
        max_sub_width = ancho - 10

        # Limitamos su tamaño máximo al tamaño ya elegido para el título
        sub_size = self.fit_text(
            self.nombre_etapa,
            max_sub_width,
            font_name="Helvetica",
            style="",           # estilo normal
            max_size=min(opt_size, 14),  # nunca más grande que el título
            min_size=6
        )

        # Dibuja subtítulo justo debajo, usando la altura de línea = sub_size
        subt_width = self.get_string_width(self.nombre_etapa)
        self.set_font("Helvetica", "", sub_size)
        # Ajusta verticalmente: bajamos del centro del banner la mitad de título + un pequeño espacio + mitad de subtítulo
        y_sub = center_y - opt_size/2 + opt_size + (sub_size * 0.2)
        self.set_xy(center_x - max_sub_width / 2, center_y + 2)
        self.cell(max_sub_width, 10, self.nombre_etapa, align='C')

        # ----- Imagen principal
        imagen_y = y_ini + alto + 10
        alto_img = self.h * 0.5
        # Dimensiones máximas deseadas
        max_w = self.w - 20
        max_h = self.h * 0.5

        try:
            # 1) obtén tamaño original
            orig_w, orig_h = imagen_ruta.size
            # 2) factor de escala
            factor = min(max_w / orig_w, max_h / orig_h)
            # 3) nuevo tamaño
            new_w = orig_w * factor
            new_h = orig_h * factor
            # 4) insertamos centrando horizontalmente
            x_img = (self.w - new_w) / 2
            self.image(imagen_ruta, x=x_img, y=imagen_y, w=new_w, h=new_h)
        except:
            self.set_xy(10, imagen_y)
            self.set_font("Helvetica", "I", 12)
            self.cell(0, 10, "(Imagen no disponible)", ew_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # --- Datos bonitos en dos cajitas iguales, con íconos y texto alineado y wrap
        self.set_y(imagen_y + alto_img + 15)

        box_w = 90
        box_h = 45
        icon_size = 15
        pad = 4       # padding interior de las cajas
        space = 10    # espacio entre cajas

        x_center = self.w / 2
        x1 = x_center - box_w - space / 2
        x2 = x_center + space / 2
        y0 = self.get_y()

        self.set_fill_color(160, 211, 180)

        # ---- Caja 1: Provincia + Comunidad Autónoma
        self.rect(x1, y0, box_w, box_h, style='F')

        line_h = 6
        # --- Provincia
        y_line = y0 + (box_h - line_h) / 4
        self.image("static/provincia.png", x1 + pad, y_line + (line_h-icon_size)*1.1, icon_size)
        self.set_xy(x1 + pad + icon_size + 2, y_line)
        self.set_font("Helvetica", "B", 12)
        self.cell( self.get_string_width("Provincia: "), line_h, "Provincia: ", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 12)
        # wrap dentro de la caja
        self.multi_cell(box_w - (pad + icon_size + 2), line_h, self.provincia)

        # --- Comunidad Autónoma
        y_line = y0 + (box_h - line_h) / 4 + 2*line_h
        self.image("static/ccaa.png", x1 + pad, y_line + (line_h-icon_size)/1.5, icon_size)
        self.set_xy(x1 + pad + icon_size + 2, y_line)
        self.set_font("Helvetica", "B", 12)
        self.multi_cell(box_w - (pad + icon_size + 2), line_h, "Comunidad Autónoma:")
        self.set_font("Helvetica", "", 12)
        self.set_x(x1 + pad + icon_size + 2)
        self.multi_cell(box_w - (pad + icon_size + 2), line_h, self.ccaa)

        # ---- Caja 2: Longitud
        self.rect(x2, y0, box_w, box_h, style='F')

        # La longitud centrada verticalmente
        y_line = y0 + (box_h - line_h) / 2
        self.image("static/longitud.png", x2 + pad, y_line + (line_h-icon_size), icon_size)
        self.set_xy(x2 + pad + icon_size + 2, y_line)
        self.set_font("Helvetica", "B", 12)
        self.cell(self.get_string_width("Longitud: "), line_h, "Longitud: ", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 12)
        self.multi_cell(box_w - (pad + icon_size + 2), line_h, f"{self.longitud} km")


    def add_grupo_header(self, grupo):
        self.set_font("Helvetica", "B", 18)
        self.set_fill_color(160, 211, 180)
        self.cell(0, 10, f"{grupo}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(3)


    def add_especie(self, nombre_cientifico, nombre_comun, descripcion, fotografia, autor, isinvasive, conservationstatus):
        # Título con nombre común y nombre científico
        self.set_font("Helvetica", "B", 13)

        if nombre_comun:
            self.write(8, f"{nombre_comun} (")
            # Parte en cursiva
            self.set_font("Helvetica", "BI", 13)
            self.write(8, " ".join(nombre_cientifico.split()[:2]))
            # Parte restante del nombre científico (si hay más)
            resto = " " + " ".join(nombre_cientifico.split()[2:]) if len(nombre_cientifico.split()) > 2 else ""
            self.set_font("Helvetica", "B", 13)
            self.write(8, f"{resto})")
        else:
            self.set_font("Helvetica", "BI", 13)
            self.write(8, " ".join(nombre_cientifico.split()[:2]))
            resto = " " + " ".join(nombre_cientifico.split()[2:]) if len(nombre_cientifico.split()) > 2 else ""
            self.set_font("Helvetica", "B", 13)
            self.write(8, resto)

        self.ln(5)

        #Estado de conservación
        if conservationstatus:
            status_label = conservationstatus
        else:
            conservationstatus = None
            status_label = "Estado de conservación desconocido"

        # Calculamos color
        rgb = self.color_map.get(status_label, (255, 255, 255))
        self.set_fill_color(*rgb)
        self.set_draw_color(0, 0, 0)

        # Parámetros del círculo
        diam = 5  # mm
        x0 = self.l_margin  # margen izquierdo
        y0 = self.get_y() + 3

        # Dibujamos el círculo
        self.ellipse(x0, y0, diam, diam, style="DF")

        # Texto al lado del círculo
        self.set_xy(x0 + diam + 1, y0)
        self.set_font("Helvetica", "B", 10)
        self.cell(self.get_string_width(status_label), diam, status_label, new_x=XPos.LMARGIN, new_y=YPos.TOP)

        # Si es invasora, mostrar advertencia justo debajo del nombre
        if isinvasive.strip().lower() == "invasora":
            # Parámetros del triángulo
            tri_size = 5  # tamaño del triángulo

            # Posición del triángulo (entre nombre y cuerpo)
            x0 = self.w - self.r_margin - self.get_string_width("Especie invasora") - 8.5
            y0 = y0

            # Coordenadas del triángulo equilátero (punta arriba)
            triangle = [
                (x0, y0 + tri_size),
                (x0 + tri_size, y0 + tri_size),
                (x0 + tri_size / 2, y0)
            ]

            # Dibujar triángulo amarillo
            self.set_fill_color(255, 204, 0)
            self.set_draw_color(0, 0, 0)
            self.polygon(triangle, style='DF')

            # Dibujar "!" encima del triángulo
            self.set_font("Helvetica", "B", 10)
            self.set_xy(x0 + 0.9, y0 + 1.75)
            self.cell(tri_size, 3, "!", new_x=XPos.RIGHT, new_y=YPos.TOP)

            # Texto al lado
            self.set_font("Helvetica", "B", 10)
            self.set_xy(x0 + tri_size + 1, y0)
            self.cell(0, 5, "Especie invasora", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            # Restaurar color y fuente
            self.set_text_color(0)
            self.set_font("Helvetica", "", 11)
            self.ln(2.5)
        else:
            self.ln(7)

        img_size = 50  # tamaño de la imagen en mm
        x_img = self.get_x()
        y_img = self.get_y()
        if fotografia is not None:
            self.image(fotografia, x=x_img, y=y_img, w=img_size, h=img_size, dims=(300,300))
        else:
            with self.local_context(fill_opacity=0.4):
                self.image("static/logocontorno.png", x=x_img, y=y_img, w=img_size, h=img_size)

        # Mueve el cursor al lado derecho de la imagen
        self.set_xy(x_img + img_size + 5, y_img)
        self.set_font("Helvetica", "", 11)
        self.multi_cell(0, 5, descripcion)

        # Volver a abajo del bloque
        self.set_y(max(self.get_y(), y_img + img_size))

        # Créditos justo debajo de la imagen
        self.set_xy(x_img, y_img + img_size + 0.5)  # 0.5 mm de separación
        self.set_font("Helvetica", "I", 9)
        if fotografia is not None:
            self.cell(0, 6, f"Créditos: {autor}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            self.cell(0, 6, "", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Luego, ajustamos el cursor para continuar después de la zona de créditos
        self.set_y(y_img + img_size + 6)  # 6 mm desde la base de la imagen para dejar espacio

        self.ln(5)


    async def create_pdf(self):
        # Establecer márgenes superior e inferior
        self.set_top_margin(20)                          # Margen superior
        self.set_auto_page_break(auto=True, margin=20)   # Margen inferior
        self.set_left_margin(15)     # Margen izquierdo
        self.set_right_margin(15)    # Margen derecho

        # Página inicial
        self.add_page()

        self.add_portada(await self.imagen_ruta_task)

        # Para cada grupo taxonómico
        # Controlar qué grupos ya se han mostrado

        grupos_mostrados = set()
        especies_por_pagina = 3
        contador_en_pagina = 0

        self.add_page()

        # Aplanar lista de especies y mantener orden por grupo
        especies_ordenadas = []
        for grupo, lista in sorted(self.especies_por_grupo.items()):
            for especie in lista:
                especies_ordenadas.append((grupo, especie))

        # Esperar a la descarga de las imágenes
        descargas = await asyncio.gather(*self.imagenes_tasks)
        imagenes = {id: desc for id, desc in zip(self.taxones, descargas)}

        for grupo, especie in especies_ordenadas:
            # Añadir grupo taxonómico si no se ha mostrado antes
            if grupo not in grupos_mostrados:
                self.add_grupo_header(grupo)
                grupos_mostrados.add(grupo)

            # Comprobar si cabe la especie en la página actual
            espacio_disponible = self.h - self.get_y() - self.b_margin
            altura_estimada_ficha = 70  # puedes ajustar si tus fichas son más o menos altas

            if espacio_disponible < altura_estimada_ficha:
                self.add_page()

            # Añadir especie
            self.add_especie(
                nombre_cientifico=especie["nombre_cientifico"],
                nombre_comun=especie["nombre_comun"],
                descripcion=especie["descripcion"],
                autor=especie["license_holder"],
                fotografia=imagenes[especie["idtaxon"]],
                isinvasive=especie["isinvasive"],
                conservationstatus=especie["conservationstatus"]
            )

            # Cuando se agregue una especie, revisamos si hemos agregado 3
            contador_en_pagina += 1

            # Pasar a la siguiente página si se ha alcanzado especies_por_pagina especies
            if contador_en_pagina == especies_por_pagina:
                # Solo agregar nueva página si no es la última especie
                if (grupo, especie) != especies_ordenadas[-1]:
                    self.add_page()
                contador_en_pagina = 0