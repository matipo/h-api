from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

URL_HORARIO = "https://ulagos.cl"

@app.get("/api/horario")
def obtener_horario():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        respuesta = requests.get(URL_HORARIO, headers=headers, timeout=10)
        
        if respuesta.status_code != 200:
            return {"error": f"Error de conexión con la Ulagos ({respuesta.status_code})"}
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        # Corrección 1: Buscamos cualquier tabla en la página si no encuentra la clase específica
        tabla = soup.find('table', class_='table-schedule') or soup.find('table')
        if not tabla:
            return {"error": "No se encontró ninguna tabla de horarios en el sitio."}
            
        cuerpo_tabla = tabla.find('tbody')
        if not cuerpo_tabla:
            return {"error": "La tabla no contiene un elemento tbody."}
            
        filas = cuerpo_tabla.find_all('tr')
        
        horario_completo = []
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

        for fila in filas:
            celdas = fila.find_all('td')
            if not celdas:
                continue
                
            # Extraer el bloque horario limpiando espacios en blanco
            bloque_hora = " ".join(celdas[0].text.split())
            ramos_del_bloque = {}
            
            # Revisar las celdas de los días (Lunes a Sábado)
            for indice, celda in enumerate(celdas[1:]):
                if indice >= len(dias_semana):
                    break
                    
                nombre_dia = dias_semana[indice]
                div_actividad = celda.find('div', class_='actividad')
                
                if div_actividad:
                    # Corrección 2: Extraemos todas las líneas de texto ignorando las etiquetas intermedias
                    lineas = [linea.strip() for linea in div_actividad.get_text(separator="\n").split("\n") if linea.strip()]
                    
                    # Inicializamos los campos vacíos por seguridad
                    nombre_ramo = lineas[0] if len(lineas) > 0 else ""
                    tipo_clase = lineas[1] if len(lineas) > 1 else ""
                    codigo_ramo = lineas[2] if len(lineas) > 2 else ""
                    grupo = lineas[3] if len(lineas) > 3 else ""
                    seccion = lineas[4] if len(lineas) > 4 else ""
                    
                    # Buscar de forma independiente el docente y la sala usando lo que contenga la cadena
                    docente = ""
                    sala = ""
                    for l in lineas:
                        if "SALA" in l.upper() or "LABORATORIO" in l.upper():
                            sala = l
                        elif any(apellido in l.upper() for apellido in ["SEGOVIA", "CARRASCO", "PROFESOR", "DOCENTE"]): 
                            # Si la línea tiene nombres o apellidos largos (y no es lo anterior), asumimos que es el docente
                            if l != nombre_ramo and l != tipo_clase and l != codigo_ramo and l != grupo and l != seccion and l != sala:
                                docente = l

                    # Si el filtrado manual de docente no engancha, usamos una posición estimada por defecto
                    if not docente and len(lineas) > 5:
                        docente = lineas[5]
                    if not sala and len(lineas) > 6:
                        sala = lineas[6]

                    ramos_del_bloque[nombre_dia] = {
                        "nombre": f"{nombre_ramo} {tipo_clase}".strip(),
                        "codigo": codigo_ramo,
                        "grupo": grupo,
                        "seccion": seccion,
                        "docente": docente,
                        "sala": sala
                    }
                else:
                    ramos_del_bloque[nombre_dia] = None
            
            horario_completo.append({
                "bloque": bloque_hora,
                "clases": ramos_del_bloque
            })
            
        return {
            "carrera": "Ingeniería Civil en Informática",
            "sede": "Puerto Montt",
            "horario": horario_completo
        }
        
    except Exception as e:
        return {"error": f"Ocurrió un error en el servidor: {str(e)}"}
