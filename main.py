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
# Estructura: { nivel_semestre: {"timestamp": float, "data": dict} }
MEMORIA_CACHE = {}
TIEMPO_EXPIRACION_CACHÉ = 86400  # Guardar los datos localmente por 24 horas (en segundos)

# URL base limpia sin el parámetro de nivel fijo
URL_BASE_ULAGOS = "https://ulagos.cl"

def mapear_html_horario(html_content):
    """Procesa el HTML crudo y lo transforma en un diccionario estructurado"""
    soup = BeautifulSoup(html_content, 'html.parser')
    tabla = soup.find('table', class_='table-schedule') or soup.find('table')
    if not tabla:
        return None
        
    cuerpo_tabla = tabla.find('tbody')
    if not cuerpo_tabla:
        return None
        
    filas = cuerpo_tabla.find_all('tr')
    horario_completo = []
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

    for fila in filas:
        clase_fila = fila.get('class', [])
        clase_fila_str = "".join(clase_fila).lower()
        if any(x in clase_fila_str for x in ['almuerzo', 'text-muted', 'table-light', 'footer']):
            continue

        celdas = fila.find_all('td')
        if not celdas or len(celdas) < 2:
            continue
            
        bloque_hora = " ".join(celdas.text.split())
        if not bloque_hora:
            continue

        ramos_del_bloque = {}
        
        for indice, celda in enumerate(celdas[1:]):
            if indice >= len(dias_semana):
                break
                
            nombre_dia = dias_semana[indice]
            div_actividad = celda.find('div', class_='actividad')
            
            if div_actividad:
                lineas = [l.strip() for l in div_actividad.get_text(separator="\n").split("\n") if l.strip()]
                
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
        
    return [b for b in horario_completo if any(b["clases"].values()) or "13:15" not in b["bloque"]]

# Endpoint optimizado con parámetro de ruta para consultar cualquier semestre (del 1 al 10)
@app.get("/api/horario/{nivel}")
def obtener_horario_por_semestre(nivel: int):
    # Validar que el semestre solicitado se encuentre en el rango académico real
    if nivel < 1 or nivel > 11 or nivel == 6:
        return {"error": "El semestre solicitado debe estar comprendido entre el 1 y el 11 exceptuando el 6."}

    tiempo_actual = time.time()
    
    # Verificación de Caché: Si el semestre ya se consultó y no ha expirado, se retorna de inmediato
    if nivel in MEMORIA_CACHE:
        cache_data = MEMORIA_CACHE[nivel]
        if tiempo_actual - cache_data["timestamp"] < TIEMPO_EXPIRACION_CACHÉ:
            return cache_data["data"]

    # Si no está en caché o ya expiró, se realiza la petición correspondiente a la universidad
    try:
        # 💻 CORRECCIÓN: Se eliminó la concatenación manual incorrecta con '&'
        # Si la URL base de la página del horario tiene una ruta específica (ej: "https://ulagos.cl"), 
        # asegúrate de cambiar el valor de URL_BASE_ULAGOS arriba en tu archivo.
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        parametros = {"nivel": nivel}
        
        # requests se encarga automáticamente de armar la URL de forma correcta usando '?'
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
        
        # Guardar el resultado en la caché en memoria antes de responderle al usuario
        MEMORIA_CACHE[nivel] = {
            "timestamp": tiempo_actual,
            "data": json_respuesta
        }
        
        return json_respuesta
        
    except Exception as e:
        return {"error": f"Fallo crítico en el procesamiento del semestre {nivel}: {str(e)}"}
