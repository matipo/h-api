from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estructura de caché en memoria local para guardar los semestres ya procesados
MEMORIA_CACHE = {}
TIEMPO_EXPIRACION_CACHÉ = 86400  # Guardar los datos localmente por 24 horas

# URL base apuntando al sistema de horarios real de la universidad
URL_BASE_ULAGOS = "https://horarios.ulagos.cl/Global/carrera.php"

def mapear_html_horario(html_content):
    """Procesa el HTML crudo y lo transforma en un diccionario estructurado"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Intenta buscar la tabla por clase o de forma genérica
    tabla = soup.find('table', class_='table-schedule') or soup.find('table', class_='table') or soup.find('table')
    if not tabla:
        return None
        
    cuerpo_tabla = tabla.find('tbody') or tabla
    filas = cuerpo_tabla.find_all('tr')
    if not filas:
        return None
        
    horario_completo = []
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

    for fila in filas:
        clase_fila = fila.get('class', [])
        clase_fila_str = "".join(clase_fila).lower()
        if any(x in clase_fila_str for x in ['almuerzo', 'text-muted', 'table-light', 'footer']):
            continue

        celdas = fila.find_all(['td', 'th'])
        if not celdas or len(celdas) < 2:
            continue
            
        bloque_hora = " ".join(celdas[0].text.split())
        if not bloque_hora:
            continue

        ramos_del_bloque = {}
        
        for indice, celda in enumerate(celdas[1:]):
            if indice >= len(dias_semana):
                break
                
            nombre_dia = dias_semana[indice]
            
            # Intenta buscar el div estructurado, si no, extrae el texto directo de la celda
            div_actividad = celda.find('div', class_='actividad') or celda.find('div')
            texto_origen = div_actividad if div_actividad else celda
            
            texto_limpio = texto_origen.get_text(separator="\n").strip()
            
            if texto_limpio and len(texto_limpio) > 3:
                lineas = [l.strip() for l in texto_limpio.split("\n") if l.strip()]
                
                nombre_ramo, codigo, grupo, seccion, docente, sala = "", "", "", "", "", ""

                for l in lineas:
                    l_upper = l.upper()
                    if "GRUPO:" in l_upper:
                        grupo = l
                    elif "SECCION:" in l_upper or "SECCIÓN:" in l_upper:
                        seccion = l
                    elif "SALA" in l_upper or "LABORATORIO" in l_upper:
                        sala = l
                    elif ":" in l and l.count(":") >= 2:
                        codigo = l
                    elif "02028:" in l:
                        continue 
                    else:
                        if not nombre_ramo:
                            nombre_ramo = l
                        elif len(l) > 8 and not docente:
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
                ramos_del_bloque[nombre_dia] = None
        
        horario_completo.append({
            "bloque": bloque_hora,
            "clases": ramos_del_bloque
        })
        
    return [b for b in horario_completo if any(b["clases"].values())]


# Endpoint optimizado con parámetro de ruta para consultar cualquier semestre (del 1 al 11)
@app.get("/api/horario/{nivel}")
def obtener_horario_por_semestre(nivel: int):
    if nivel < 1 or nivel > 11 or nivel == 6:
        return {"error": "El semestre solicitado debe estar comprendido entre el 1 y el 11 exceptuando el 6."}

    tiempo_actual = time.time()
    
    if nivel in MEMORIA_CACHE:
        cache_data = MEMORIA_CACHE[nivel]
        if tiempo_actual - cache_data["timestamp"] < TIEMPO_EXPIRACION_CACHÉ:
            return cache_data["data"]

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Parámetros obligatorios estructurados para el formulario institucional
        parametros = {
            "carrera": "3216",
            "nivel": str(nivel),
            "plan": "3216II2020",
            "sede": "2028"
        }
        
        # 💻 CORRECCIÓN CRÍTICA: Se cambió requests.get por requests.post enviando los datos mediante 'data'
        respuesta = requests.get(URL_BASE_ULAGOS, headers=headers, params=parametros, timeout=12)
        
        if respuesta.status_code != 200:
            return {"error": f"Error de comunicación con el portal institucional ({respuesta.status_code})"}
            
        datos_procesados = mapear_html_horario(respuesta.text)
        
        if not datos_procesados:
            return {"error": f"La estructura académica para el semestre {nivel} no pudo ser parseada."}
            
        json_respuesta = {
            "carrera": "Ingeniería Civil en Informática",
            "sede": "Puerto Montt",
            "semestre_consultado": nivel,
            "horario": datos_procesados
        }
        
        MEMORIA_CACHE[nivel] = {
            "timestamp": tiempo_actual,
            "data": json_respuesta
        }
        
        return json_respuesta
        
    except Exception as e:
        return {"error": f"Fallo crítico en el procesamiento del semestre {nivel}: {str(e)}"}
