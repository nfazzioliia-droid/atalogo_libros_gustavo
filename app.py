import streamlit as st
from google import genai
import json

st.set_page_config(page_title="Prueba Gemini", page_icon="🔬")
st.title("🧪 Prueba de conexión con Gemini")

foto = st.camera_input("📸 Toma una foto de la portada")

if foto:
    with st.spinner("Consultando a Gemini..."):
        try:
            # Obtener clave de los secretos
            gemini_key = st.secrets["GEMINI_API_KEY"]
            cliente = genai.Client(api_key=gemini_key.strip())
            
            # Preparar la imagen
            bytes_data = foto.getvalue()
            
            # Prompt muy simple
            prompt = "Describe brevemente lo que ves en esta imagen."
            
            respuesta = cliente.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    genai.types.Part.from_bytes(data=bytes_data, mime_type="image/jpeg"),
                    prompt
                ]
            )
            
            st.success("✅ Gemini respondió correctamente:")
            st.write(respuesta.text)
            
            # Ahora intentamos extraer título y autor con otro prompt
            prompt2 = "Extrae el título y el autor de este libro de la imagen. Responde en formato JSON: {\"titulo\": \"...\", \"autor\": \"...\"}"
            respuesta2 = cliente.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    genai.types.Part.from_bytes(data=bytes_data, mime_type="image/jpeg"),
                    prompt2
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            datos = json.loads(respuesta2.text)
            st.subheader("📚 Datos extraídos:")
            st.write(f"**Título:** {datos.get('titulo', 'No detectado')}")
            st.write(f"**Autor:** {datos.get('autor', 'No detectado')}")
            
        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.info("Revisa que tu clave de Gemini sea correcta y que la imagen sea clara.")
