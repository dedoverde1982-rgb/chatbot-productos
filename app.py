import streamlit as st
import sqlite3
import requests

# =========================
# 1) CONFIG: OpenAI y DB
# =========================

# En Streamlit Cloud, define OPENAI_API_KEY en "Settings > Secrets"
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

DB_PATH = "productos.db"  # archivo SQLite que generaste


# =========================
# 2) FUNCIONES DE BASE DE DATOS (SQLite)
# =========================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def buscar_productos_por_texto(texto_busqueda, limite=5):
    conn = get_connection()
    cur = conn.cursor()

    patron = f"%{texto_busqueda.lower()}%"

    query = """
        SELECT prod_id, prod_name, prod_desc, prod_currency,
               prod_price, prod_family, prod_subfamily,
               prod_min_stock, status, prod_photo
        FROM tbl_product
        WHERE status = 1
          AND (
                LOWER(prod_name)      LIKE ?
             OR LOWER(prod_desc)      LIKE ?
             OR LOWER(prod_family)    LIKE ?
             OR LOWER(prod_subfamily) LIKE ?
          )
        ORDER BY prod_name
        LIMIT ?;
    """

    cur.execute(query, (patron, patron, patron, patron, limite))
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return rows


# =========================
# 3) LIMPIAR TEXTO DE BÚSQUEDA
# =========================

def extraer_texto_busqueda(pregunta: str) -> str:
    pregunta = pregunta.strip().lower()

    if "producto" in pregunta or "productos" in pregunta:
        return ""

    palabras = [p.strip(".,;:¡!¿?") for p in pregunta.split()]

    stopwords = {
        "tengo", "tienes", "tienen", "tenemos",
        "quiero", "quisiera", "busco", "buscando",
        "estoy", "estamos", "en", "la", "el", "los", "las",
        "un", "una", "unos", "unas",
        "de", "del", "al", "para", "por", "con", "sobre",
        "necesito", "necesitamos",
        "busquedad", "busqueda"
    }

    palabras_clave = [p for p in palabras if p and p not in stopwords]

    if not palabras_clave:
        return pregunta

    unidades = {"gb", "tb", "mb", "hz", "mhz", "ghz"}
    if len(palabras_clave) >= 2:
        penultima = palabras_clave[-2]
        ultima = palabras_clave[-1]
        if penultima.isdigit() and ultima in unidades:
            return penultima + ultima  # "128gb"

    palabra = palabras_clave[-1]

    if len(palabra) > 4 and palabra.endswith("es"):
        palabra = palabra[:-2]
    elif len(palabra) > 3 and palabra.endswith("s"):
        palabra = palabra[:-1]

    return palabra


# =========================
# 4) LLAMADA A OPENAI (ChatGPT)
# =========================

def llamar_llm(pregunta_usuario, productos_encontrados):
    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    if productos_encontrados:
        resumen_productos = []
        for p in productos_encontrados:
            resumen_productos.append(
                f"- ID: {p['prod_id']}, Nombre: {p['prod_name']}, "
                f"Descripción: {p['prod_desc']}, "
                f"Precio: {p['prod_currency']} {p['prod_price']}, "
                f"Familia: {p['prod_family']}, Subfamilia: {p['prod_subfamily']}, "
                f"Foto: {p['prod_photo']}"
            )
        texto_productos = "\n".join(resumen_productos)
    else:
        texto_productos = "No se encontraron productos que coincidan."

    system_message = (
        "Eres un chatbot amable de una tienda de productos.\n"
        "Responde siempre en español.\n"
        "Solo puedes responder usando la información de la lista de productos "
        "que te doy a continuación.\n"
        "Si la lista está vacía, solo debes indicar que no hay productos que coincidan."
    )

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_message},
            {
                "role": "assistant",
                "content": (
                    "Esta es la lista de productos disponibles en la base de datos:\n"
                    f"{texto_productos}"
                )
            },
            {"role": "user", "content": pregunta_usuario}
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 200:
        return (
            f"Tengo un problema al llamar al modelo (código {response.status_code}). "
            "Por favor revisa la API key, el modelo o la configuración de tu cuenta."
        )

    respuesta_json = response.json()
    return respuesta_json["choices"][0]["message"]["content"]


# =========================
# 5) INTERFAZ STREAMLIT
# =========================

st.set_page_config(page_title="Chatbot de Productos", page_icon="🛍️")

st.title("🛍️ Chatbot de Productos (Demo)")
st.write("Escribe una pregunta o palabra clave, por ejemplo: *“tienes monitores de 27”*, *“usb 128 gb”*, etc.")

pregunta = st.text_input("Tu pregunta:")

if st.button("Consultar") and pregunta.strip():
    texto_busqueda = extraer_texto_busqueda(pregunta)
    productos = buscar_productos_por_texto(texto_busqueda)

    if not productos:
        st.warning("Lo siento, solo puedo responder sobre los productos de la tabla (no se encontraron coincidencias).")
    else:
        respuesta = llamar_llm(pregunta, productos)

        st.subheader("Respuesta del chatbot")
        st.write(respuesta)

        st.subheader("Productos utilizados como contexto")
        for p in productos:
            with st.container(border=True):
                st.markdown(f"**{p['prod_name']}** (ID: `{p['prod_id']}`)")
                st.write(p["prod_desc"])
                st.write(f"Precio: {p['prod_currency']} {p['prod_price']}")
                st.write(f"Familia: {p['prod_family']} / {p['prod_subfamily']}")
                if p["prod_photo"]:
                    st.image(p["prod_photo"], width=200)
else:
    st.info("Ingresa una pregunta y pulsa **Consultar** para probar el chatbot.")
