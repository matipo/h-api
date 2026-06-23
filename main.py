from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup

app = FastAPI()

# Configuración de CORS obligatoria para que consumas la API desde tu Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

URL_HORARIO = "https://horarios.ulagos.cl/Global/carrera.php?carrera=3216&nivel=1&plan=3216II2020&sede=2028"

@app.get("/api/horario")
def obtener_horario():
    try:
        # User-Agent para simular un navegador real y evitar bloqueos de la universidad
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        respuesta = requests.get(URL_HORARIO, headers=headers, timeout=12)
        
        if respuesta.status_code != 200:
            return {"error": f"No se pudo conectar a la Ulagos. Código de estado: {respuesta.status_code}"}
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        # Localizar la tabla de horarios
        tabla = soup.find('table', class_='table-schedule') or soup.find('table')
        if not tabla:
            return {"error": "Estructura de tabla inválida o modificada en el portal de la universidad."}
            
        cuerpo_tabla = tabla.find('tbody')
        if not cuerpo_tabla:
            return {"error": "No se encontró el elemento tbody dentro de la tabla."}
            
        filas = cuerpo_tabla.find_all('tr')
        
        horario_completo = []
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

        for fila in filas:
            # 1. Filtro estricto para saltar filas vacías o decorativas (como la de almuerzo o notas al pie)
            clase_fila = fila.get('class', [])
            clase_fila_str = "".join(clase_fila).lower()
            if any(x in clase_fila_str for x in ['almuerzo', 'text-muted', 'table-light', 'footer']):
                continue

            celdas = fila.find_all('td')
            # Si no contiene al menos la celda de la hora y un día, la ignoramos
            if not celdas or len(celdas) < 2:
                continue
                
            # Limpiar el bloque de la hora (Ejemplo: "1 08:30 - 09:15")
            bloque_hora = " ".join(celdas[0].text.split())
            if not bloque_hora:
                continue

            ramos_del_bloque = {}
            
            # 2. Recorrer de forma exacta las celdas correspondientes a los 6 días académicos
            for indice, celda in enumerate(celdas[1:]):
                if indice >= len(dias_semana):
                    break
                    
                nombre_dia = dias_semana[indice]
                div_actividad = celda.find('div', class_='actividad')
                
                if div_actividad:
                    # Extraemos todas las cadenas de texto del bloque de la materia limpiando espacios vacíos
                    lineas = [l.strip() for l in div_actividad.get_text(separator="\n").split("\n") if l.strip()]
                    
                    # Inicializamos los campos vacíos predeterminados
                    nombre_ramo = ""
                    codigo = ""
                    grupo = ""
                    seccion = ""
                    docente = ""
                    sala = ""

                    # 3. Lógica inteligente basada en el contenido real de los textos extraídos
                    for l in lineas:
                        l_upper = l.upper()
                        if "GRUPO:" in l_upper:
                            grupo = l
                        elif "SECCION:" in l_upper or "SECCIÓN:" in l_upper:
                            seccion = l
                        elif "SALA" in l_upper or "LABORATORIO" in l_upper:
                            sala = l
                        elif ":" in l and l.count(":") >= 2: # Detecta códigos de ramo complejos tipo "CBI01:3216:2028:1"
                            codigo = l
                        elif "02028:" in l: # Filtramos e ignoramos metadatos internos de campus (ej: 02028:S202CCH)
                            continue 
                        else:
                            # Si es la primera línea de texto legible y no cumple lo anterior, es el Nombre de la materia
                            if not nombre_ramo:
                                nombre_ramo = l
                            # Si ya tenemos el nombre de la materia pero la línea sigue siendo texto en mayúsculas largo, es el Docente
                            elif len(l) > 8 and not docente:
                                # Evaluamos si contiene el tipo de clase para anexarlo al título (ej: "(CATEDRA)" o "(PRACTICO/TALLER)")
                                if "(" in l or ")" in l:
                                    nombre_ramo += f" {l}"
                                else:
                                    docente = l

                    ramos_del_bloque[nombre_dia] = {
                        "nombre": nombre_ramo.strip(),
                        "codigo": codigo.strip(),
                        "grupo": grupo.strip(),
                        "seccion": seccion.strip(),
                        "docente": docente.strip(),
                        "sala": sala.strip()
                    }
                else:
                    # Si no hay div de actividad, este bloque y día específico están totalmente libres
                    ramos_del_bloque[nombre_dia] = None
            
            horario_completo.append({
                "bloque": bloque_hora,
                "clases": ramos_del_bloque
            })
            
        return {
            "carrera": "Ingeniería Civil en Informática",
            "sede": "Puerto Montt",
            "plan": "3216II2020",
            "horario": [b for b in horario_completo if any(b["clases"].values()) or "13:15" not in b["bloque"]] 
            # El filtro final remueve bloques totalmente vacíos que ensucian el JSON si no tienen clases asociadas
        }
        
    except Exception as e:
        return {"error": f"Fallo crítico en el procesamiento de datos: {str(e)}"}
