import streamlit as st
import gspread
import requests
import json
import re
from google import genai
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Escáner de Libros", page_icon="📚")
st.title("📚 Escáner Automático de Libros")

# ------------------------------------------------------------
# CONEXIÓN A GOOGLE SHEETS
# ------------------------------------------------------------
@st.cache_resource
def conectar_sheets():
    # Los secretos en Streamlit ahora los guardaremos como un solo string JSON
    creds_json = st.secrets["GOOGLE_CREDENTIALS_JSON"]  # <--- NOMBRE NUEVO
    creds_dict = json.loads(creds_json)
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    # La hoja debe llamarse EXACTAMENTE "Catálogo Biblioteca"
    return client.open("Catálogo Biblioteca").sheet1

# ------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ------------------------------------------------------------
def procesar_portada(image_file, gemini_key):
    cliente = genai.Client(api_key=gemini_key.strip())
    bytes_data = image_file.getvalue()

    # --- PROMPT MEJORADO ---
    prompt = """
    Eres un experto en reconocer portadas de libros.
    Extrae el TÍTULO y el AUTOR de esta imagen.
    Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional.
    Si no estás seguro, escribe "Desconocido" en el campo correspondiente.
    Formato exacto:
    {"titulo": "titulo del libro", "autor": "nombre del autor"}
    """

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
        # Intentamos parsear el JSON
        datos = json.loads(respuesta.text)
        titulo = datos.get("titulo", "Desconocido")
        autor = datos.get("autor", "Desconocido")

    except Exception as e:
        # Si falla, mostramos el error en la app para depurar
        st.error(f"Error al leer la portada con Gemini: {e}")
        return None

    # Si no se detectó nada, salimos
    if titulo == "Desconocido" and autor == "Desconocido":
        st.warning("Gemini no pudo identificar título ni autor. Prueba con otra foto.")
        return None

    # --------------------------------------------------------
    # BUSCAR EN GOOGLE BOOKS
    # --------------------------------------------------------
    try:
        query = f"intitle:{requests.utils.quote(titulo)}+inauthor:{requests.utils.quote(autor)}"
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}"
        gb_res = requests.get(url).json()
        editorial = "S/D"
        anio = "S/D"
        paginas = "S/D"
        if "items" in gb_res and len(gb_res["items"]) > 0:
            info = gb_res["items"][0]["volumeInfo"]
            editorial = info.get("publisher", "S/D")
            anio = info.get("publishedDate", "S/D")[:4]
            paginas = str(info.get("pageCount", "S/D"))
    except Exception as e:
        st.warning(f"No pude consultar Google Books: {e}")
        editorial = "Error"
        anio = "Error"
        paginas = "Error"

    # --------------------------------------------------------
    # PRECIO EN MERCADO LIBRE
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # GUARDAR EN GOOGLE SHEETS
    # --------------------------------------------------------
    try:
        sheet = conectar_sheets()
        sheet.append_row([titulo, autor, editorial, anio, paginas, precio])
        return titulo, autor, editorial, anio, paginas, precio
    except Exception as e:
        st.error(f"Error al guardar en Sheets: {e}")
        return None

# ------------------------------------------------------------
# INTERFAZ DE USUARIO
# ------------------------------------------------------------
foto = st.camera_input("📸 Sacale una foto a la portada")

if foto:
    with st.spinner("🔍 Analizando portada y buscando información..."):
        try:
            gemini_key = st.secrets["GEMINI_API_KEY"]
            resultado = procesar_portada(foto, gemini_key)
            if resultado:
                t, a, ed, an, p, pr = resultado
                st.success("✅ ¡Libro guardado exitosamente!")
                st.write(f"**Título:** {t}")
                st.write(f"**Autor:** {a}")
                st.write(f"**Editorial:** {ed}")
                st.write(f"**Año:** {an}")
                st.write(f"**Páginas:** {p}")
                st.write(f"**Precio estimado:** {pr}")
        except Exception as e:
            st.error(f"Ocurrió un error general: {e}")
