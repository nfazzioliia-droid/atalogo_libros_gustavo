import streamlit as st
import gspread
import requests
import json
from google import genai
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Escáner de Libros", page_icon="📚")
st.title("📚 Escáner Automático de Libros")

@st.cache_resource
def conectar_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["GOOGLE_CREDENTIALS"]
    if isinstance(creds_info, str):
        creds_dict = json.loads(creds_info)
    else:
        creds_dict = creds_info
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("Catálogo Biblioteca").sheet1

def procesar_portada(image_file, gemini_key):
    try:
        cliente = genai.Client(api_key=gemini_key.strip())
    except Exception as e:
        st.error(f"Error al crear cliente Gemini: {e}")
        return None

    bytes_data = image_file.getvalue()
    
    prompt = "Extrae el título y el autor de esta portada. Responde ÚNICAMENTE un objeto JSON válido sin texto adicional. Formato: {\"titulo\": \"...\", \"autor\": \"...\"}"
    
    try:
        respuesta = cliente.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                genai.types.Part.from_bytes(data=bytes_data, mime_type="image/jpeg"),
                prompt
            ],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        # Mostrar el texto devuelto para depuración (solo si estás en pruebas)
        # st.write("Respuesta de Gemini:", respuesta.text)
        
        try:
            datos = json.loads(respuesta.text)
        except json.JSONDecodeError as e:
            st.error(f"Gemini no devolvió JSON válido: {e}")
            st.write("Texto recibido:", respuesta.text)
            return None
        
        titulo = datos.get("titulo", "Desconocido")
        autor = datos.get("autor", "Desconocido")
        
        if titulo == "Desconocido" and autor == "Desconocido":
            st.warning("Gemini no pudo extraer título ni autor. Intenta con otra foto.")
            return None

    except Exception as e:
        st.error(f"Error al llamar a Gemini: {e}")
        return None

    # Buscar en Google Books
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q=intitle:{requests.utils.quote(titulo)}+inauthor:{requests.utils.quote(autor)}"
        gb_res = requests.get(url).json()
        editorial = "S/D"
        anio = "S/D"
        paginas = "S/D"
        if "items" in gb_res and len(gb_res["items"]) > 0:
            info = gb_res["items"][0]["volumeInfo"]
            editorial = info.get("publisher", "S/D")
            anio = info.get("publishedDate", "S/D")[:4]
            paginas = str(info.get("pageCount", "S/D"))
    except:
        editorial = "Error"
        anio = "Error"
        paginas = "Error"

    # Precio en Mercado Libre
    precio = "Consultar"
    try:
        ml_url = f"https://api.mercadolibre.com/sites/MLA/search?q=libro%20{requests.utils.quote(titulo)}"
        ml_res = requests.get(ml_url).json()
        if "results" in ml_res and len(ml_res["results"]) > 0:
            precios = [r["price"] for r in ml_res["results"][:5]]
            promedio = sum(precios) / len(precios)
            precio = f"${int(promedio):,} ARS"
    except:
        pass

    # Guardar en Google Sheets
    try:
        sheet = conectar_sheets()
        sheet.append_row([titulo, autor, editorial, anio, paginas, precio])
        return titulo, autor, editorial, anio, paginas, precio
    except Exception as e:
        st.error(f"Error al guardar en Sheets: {e}")
        return None

# Interfaz
foto = st.camera_input("📸 Sacale una foto a la portada")
if foto:
    with st.spinner("🔍 Analizando..."):
        try:
            gemini_key = st.secrets["GEMINI_API_KEY"]
            resultado = procesar_portada(foto, gemini_key)
            if resultado:
                t, a, ed, an, p, pr = resultado
                st.success("✅ ¡Guardado!")
                st.write(f"**Título:** {t}")
                st.write(f"**Autor:** {a}")
                st.write(f"**Editorial:** {ed}")
                st.write(f"**Año:** {an}")
                st.write(f"**Páginas:** {p}")
                st.write(f"**Precio estimado:** {pr}")
        except Exception as e:
            st.error(f"Error general: {e}")
