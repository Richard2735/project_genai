"""
interface/app.py — Interfaz web con Streamlit

Interfaz gráfica opcional para interactuar con el agente desde el navegador.

Uso:
    streamlit run interface/app.py
"""

import streamlit as st
import sys
import os

# Agregar el directorio raíz al path para importar agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import setup_agent

st.set_page_config(
    page_title="Agente IA - Módulo II",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Agente Inteligente con LangChain")
st.caption("Proyecto Integrador Módulo II — Herramientas: data_prep | rag_search | dlp_anonymizer")

# Inicializar agente y historial en session_state
if "agent_executor" not in st.session_state:
    with st.spinner("Iniciando agente..."):
        st.session_state.agent_executor = setup_agent()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar historial de mensajes
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input del usuario
if prompt := st.chat_input("Escribe tu mensaje..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            response = st.session_state.agent_executor.invoke({"input": prompt})
            answer = response["output"]
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
