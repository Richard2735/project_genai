"""
agent.py — Archivo principal del Agente Inteligente Módulo II

Este script configura y ejecuta un AgentExecutor de LangChain con 3 herramientas
personalizadas (data_prep, rag_search, dlp_anonymizer), memoria de corto plazo,
y LLM Gemini via Vertex AI o Google AI Studio.

Requisitos:
  - pip install langchain langchain-google-vertexai python-dotenv
  - USE_VERTEX_AI=true en .env (con gcloud auth configurado)

Uso:
  python agent.py
"""

import os
from dotenv import load_dotenv
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_classic.memory import ConversationBufferWindowMemory
from langchain_classic import hub

# Importar herramientas personalizadas
from tools.data_prep import data_prep_tool
from tools.rag_search import rag_search_tool
from tools.dlp_anonymizer import dlp_anonymizer_tool

# Cargar variables de entorno (.env)
load_dotenv()

def setup_agent():
    """
    Configura e inicializa el AgentExecutor con todas las herramientas
    y memoria de conversación.

    Returns:
        AgentExecutor: Agente listo para invocar
    """

    # 1. Configurar LLM (Gemini 2.0 Flash via Google AI Studio)
    # Usamos siempre ChatGoogleGenerativeAI con API key para el LLM.
    # Vertex AI se usa solo para embeddings (text-embedding-004) en la ingesta.
    from langchain_google_genai import ChatGoogleGenerativeAI
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "⚠️  No se encontró GOOGLE_API_KEY en .env\n"
            "Por favor, configura: GOOGLE_API_KEY=tu_api_key"
        )
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.1,
    )
    print("  🔧 LLM: Gemini 2.0 Flash (Google AI Studio)")

    # 2. Memoria de corto plazo (últimos 5 turnos de conversación)
    memory = ConversationBufferWindowMemory(
        memory_key="chat_history",
        k=5,  # Mantiene los últimos 5 turnos
        return_messages=True
    )

    # 3. Lista de herramientas personalizadas
    tools = [data_prep_tool, rag_search_tool, dlp_anonymizer_tool]

    # 4. Prompt del agente (ReAct pattern - Reasoning + Acting)
    # hwchase17/react-chat es un prompt especializado para chat con tools
    prompt = hub.pull("hwchase17/react-chat")

    # 5. Crear agente (ReAct)
    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)

    # 6. Ejecutor con manejo de errores y límite de iteraciones
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,  # Mostrar razonamiento paso a paso
        handle_parsing_errors=True,
        max_iterations=5
    )

    return agent_executor

def main():
    """Bucle principal de conversación con el agente."""

    print("\n" + "="*70)
    print("🤖 Agente IA - Proyecto Integrador Módulo II")
    print("="*70)
    print("Herramientas disponibles:")
    print("  1. data_prep_tool     → Limpia y convierte texto a JSONL")
    print("  2. rag_search_tool    → Busca en documentos corporativos")
    print("  3. dlp_anonymizer_tool → Enmascara datos sensibles (PII)")
    print("\nEscribe 'salir' para terminar.")
    print("="*70 + "\n")

    try:
        agent_executor = setup_agent()
    except ValueError as e:
        print(f"❌ Error de configuración: {e}")
        return

    # Bucle de conversación
    while True:
        try:
            user_input = input("Tú: ").strip()

            if user_input.lower() == "salir":
                print("👋 ¡Hasta luego!")
                break

            if not user_input:
                continue

            print("\n🤔 Pensando...\n")
            response = agent_executor.invoke({"input": user_input})
            print(f"\nAgente: {response['output']}\n")

        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    main()
