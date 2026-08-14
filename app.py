import streamlit as st
import gspread
import requests
import json
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Escáner de Libros", page_icon="📚")
st.title("📚 Escáner Automático de Libros")

# Configurar Google Sheets a través de los Secrets de Streamlit
@st.cache_resource
def conectar_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("Catálogo Biblioteca").sheet1

# Función para procesar foto y buscar datos
def procesar_portada_y_guardar(image_file, api_key):
    # 1. OCR / Visión con OpenAI
    import base64
    bytes_data = image_file.getvalue()
    base64_image = base64.b64encode(bytes_data).decode('utf-8')

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extrae el título y autor del libro de esta portada. Responde ÚNICAMENTE un JSON con formato: {\"titulo\": \"...\", \"autor\": \"...\"}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }],
        "response_format": {"type": "json_object"}
    }
    
    res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload).json()
    datos = json.loads(res['choices'][0]['message']['content'])
    
    titulo = datos.get("titulo", "Desconocido")
    autor = datos.get("autor", "Desconocido")

    # 2. Buscar metadata en Google Books API
    gb_url = f"https://www.googleapis.com/books/v1/volumes?q=intitle:{titulo}+inauthor:{autor}"
    gb_res = requests.get(gb_url).json()
    
    editorial = "S/D"
    anio = "S/D"
    paginas = "S/D"
    
    if "items" in gb_res and len(gb_res["items"]) > 0:
        info = gb_res["items"][0]["volumeInfo"]
        editorial = info.get("publisher", "S/D")
        anio = info.get("publishedDate", "S/D")[:4]
        paginas = str(info.get("pageCount", "S/D"))

    # 3. Estimar precio promedio online
    precio_estimado = "Consultar"
    try:
        precio_url = f"https://api.mercadolibre.com/sites/MLA/search?q=libro%20{titulo}"
        ml_res = requests.get(precio_url).json()
        if "results" in ml_res and len(ml_res["results"]) > 0:
            precios = [r["price"] for r in ml_res["results"][:5]]
            promedio = sum(precios) / len(precios)
            precio_estimado = f"${int(promedio):,} ARS"
    except:
        pass

    # 4. Guardar en Google Sheets
    sheet = conectar_sheets()
    sheet.append_row([titulo, autor, editorial, anio, paginas, precio_estimado])
    return titulo, autor, editorial, anio, paginas, precio_estimado

# Interfaz gráfica
foto = st.camera_input("Sacale una foto a la portada")
if foto:
    st.info("Procesando la portada e ingresando al catálogo...")
    try:
        openai_key = st.secrets["OPENAI_API_KEY"]
        t, a, ed, an, p, pr = procesar_portada_y_guardar(foto, openai_key)
        st.success(f"¡Guardado con éxito!\n\n**Título:** {t}\n**Autor:** {a}\n**Editorial:** {ed}\n**Año:** {an}\n**Páginas:** {p}\n**Precio Estimado:** {pr}")
    except Exception as e:
        st.error(f"Error al procesar: {e}")
