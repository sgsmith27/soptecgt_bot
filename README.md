# Chatbot de Soporte Técnico con RAG, LLMs y Rasa

Este proyecto implementa un **chatbot inteligente de soporte técnico**, desarrollado como parte del Trabajo Final de Máster en Inteligencia Artificial.  
El sistema integra técnicas avanzadas de:

- Procesamiento del Lenguaje Natural (Rasa)
- Recuperación aumentada por generación (**RAG**) con embeddings
- Modelos de Lenguaje Grandes (LLM)
- Evaluación automática de calidad con **DeepEval**
- Motor de tickets y dashboard de incidentes (Streamlit)
- Integración con Telegram como canal de atención 24/7

El chatbot está orientado a soportar al departamento de **SopTeC** para reducir carga operativa y brindar soluciones guiadas a problemas frecuentes de hardware y software.

---

# Arquitectura General

El sistema completo está compuesto por:

- **Rasa NLU + Core** → manejo de intents, entidades y diálogos guiados
- **Motor RAG propio** → búsqueda semántica por categoría y subcategoría
- **Self-Query Retrieval (opcional)** → reformulación semántica y clasificación automática
- **LLM local/cloud** → fallback para categorías no cubiertas
- **Dashboard de incidentes** (Streamlit)
- **Bridge de Telegram** para interacción con usuarios finales
- **Evaluación con DeepEval** (relevancy, faithfulness, contextual relevance)

Se incluye además una base de conocimiento en formato `.md` estructurada por categorías.

---

# Puesta en Marcha

## 1. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

## 2. Instalar dependencias
pip install -r requirements.txt

## 3. configurar variable de entorno
cp .env.example .env

## 4. Ejecutar cada componente

### 4.1 Rasa server
rasa run --enable-api --cors "*"

### 4.2 Actions server
rasa run actions

### 4.3 Telegram Bridge
python telegram_bridge.py

### 4.4 Dashboard de incidentes
streamlit run dashboard_incidentes.py

### 4.5 Evaluación RAG (opcional)
python evaluate_rag.py

Evaluación Automática (DeepEval)

El proyecto incluye un script evaluate_rag.py que mide:

Answer Relevancy

Contextual Relevancy

Faithfulness

Utilizando DeepEval y un conjunto de casos de prueba definidos.

Los resultados permiten comparar arquitecturas (RAG estándar / Self-query / etc).


# Estructura del Proyecto
/actions.py

/domain.yml

/nlu.yml

/rules.yml

/config.yml

/endpoints.yml


/rag_engine.py

/rag_index.py

/kb_index_meta.json

/base_conocimiento/*.md


/telegram_bridge.py

/dashboard_incidentes.py


/evaluate_rag.py

/manual_evaluate_rag.py


requirements.txt

README.md


# Autor
Sergio G. Smith

Dec 2025

UG

<img width="948" height="1326" alt="ARQUITECTURA GENERAL" src="https://github.com/user-attachments/assets/6fa2c14a-bd66-46b2-862d-b29d906a5faa" />


