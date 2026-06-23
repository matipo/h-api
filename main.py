from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup

app = FastAPI()

# Permite que tu frontend consulte esta API sin problemas de CORS
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
        # 1. Descargar el HTML de la Universidad de Los Lagos
        headers = {"User-Agent": "Mozilla/5.0"}
        respuesta = requests.get(URL_HORARIO, headers=headers, timeout=10)
        
        if respuesta.status_code != 200:
            return {"error": f"Error de conexión con la U. de Los Lagos ({respuesta.status_code})"}
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        # 2. Buscar la tabla del horario
        tabla = soup.find('table', class_='table-schedule')
        if not tabla:
            return {"error": "No se encontró la tabla de horarios en el sitio."}
            
        cuerpo_tabla = tabla.find('tbody')
        filas = cuerpo_tabla.find_all('tr')
        
        horario_completo = []
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

        # 3. Recorrer cada bloque de hora (cada fila <tr>)
        for fila in filas:
            celdas = fila.find_all('td')
            if not celdas:
                continue
                
            # La primera celda (index 0) corresponde a la hora del bloque (ej: 08:30 - 09:15)
            # Quitamos espacios extras y saltos de línea con strip()
            bloque_hora = celdas[0].text.strip().replace('\n', ' ')
            
            ramos_del_bloque = {}
            
            # Recorrer los días de la semana (celdas de la 1 en adelante)
            for indice, celda in enumerate(celdas[1:]):
                if indice >= len(dias_semana):
                    break
                    
                nombre_dia = dias_semana[indice]
                div_actividad = celda.find('div', class_='actividad')
                
                # Si hay clase en este bloque y día
                if div_actividad:
                    # Buscamos todos los campos internos usando los ids que se ven en tu imagen
                    spans = div_actividad.find_all('span', id='mat')
                    
                    # Estructuramos la info de forma segura evitando errores si falta algún dato
                    info_ramo = {
                        "nombre": spans[0].text.strip() if len(spans) > 0 else "",
                        "codigo": spans[1].text.strip() if len(spans) > 1 else "",
                        "grupo": spans[2].text.strip() if len(spans) > 2 else "",
                        "seccion": spans[3].text.strip() if len(spans) > 3 else "",
                        "docente": div_actividad.find('span', id='docente').text.strip() if div_actividad.find('span', id='docente') else "",
                        "sala": div_actividad.find('span', id='carrera').text.strip() if div_actividad.find('span', id='carrera') else ""
                    }
                    ramos_del_bloque[nombre_dia] = info_ramo
                else:
                    # Bloque libre para este día
                    ramos_del_bloque[nombre_dia] = None
            
            # Guardamos la fila procesada
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
