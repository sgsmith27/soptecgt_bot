"""
Evaluación del motor RAG usando DeepEval
"""

import os
from typing import List, Dict, Optional

os.environ["DEEPEVAL_TELEMETRY"] = "0"
os.environ["OPENAI_API_REQUEST_TIMEOUT"] = "60"
os.environ["OPENAI_API_MAX_RETRIES"] = "5"

# Motor RAG
from rag_engine import buscar_soluciones

# DeepEval
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)

#CASOS DE PRUEBA
TEST_CASES = [
    {
        "name": "Computadora no enciende",
        "categoria": "computadora",
        "subcategoria": None,
        "query": "Mi computadora no enciende, no muestra luces ni sonido.",
        "expected": (
            "1. **Verificar toma de corriente y regleta**"
            "- Conecta la computadora **directamente a la pared**, si es posible"
            "- Si usas regleta, verifica que esté **encendida** y funcionando (prueba otro dispositivo)." 
        ),
    },
    {
        "name": "Monitor pantalla negra",
        "categoria": "monitor",
        "subcategoria": None,
        "query": "El CPU parece encender pero el monitor se queda en negro.",
        "expected": (
            "1. **Verificar que el monitor esté encendido**"
            "- Confirmar que el LED esté iluminado (verde o ámbar)."
            "- Si está parpadeando, puede estar entrando en modo de reposo."
        ),
    },
    {
        "name": "Impresora térmica no imprime",
        "categoria": "impresora_termica",
        "subcategoria": None,
        "query": "La impresora térmica de caja no imprime tickets",
        "expected": (
            "1. **Verificar estado de la impresora**"
            "- Confirmar que el LED de **POWER** esté encendido."
            "- Si la luz de **ERROR** está fija o parpadeando, revisar tapa y papel."
        ),
    },
    {
        "name": "Scanner no jala hojas",
        "categoria": "scannersfin",
        "subcategoria": None,
        "query": "El escaner no jala las hojas, al parecer se quedan trabadas",
        "expected": (
            "1. **Alinear correctamente el papel**"
            "- Verifica que las hojas estén **rectas y sin dobleces**."
            "- Asegúrate de que no haya grapas, clips o papeles pegados."
            "- Coloca el papel con el lado correcto hacia abajo (según modelo)."
        ),
    },
]


# 2) Procesamiento del resultado RAG → contexto DeepEval
def build_context_from_rag_result(rag_result: Dict) -> str:
    """Convierte un resultado del RAG en un string plano para evaluación."""
    content = rag_result.get("content", "")
    title = rag_result.get("title", "")
    path = rag_result.get("path", "")
    category = rag_result.get("category", "")

    return f"TITULO: {title}\nRUTA: {path}\nCATEGORIA: {category}\n\n{content}"


def run_rag(query: str, categoria: Optional[str], subcategoria: Optional[str]) -> str:
    """Ejecuta el RAG con buscar_soluciones."""
    resultados = buscar_soluciones(
        descripcion=query,
        categoria=categoria,
        subcategoria=subcategoria,
        top_k=1,
    )

    if not resultados:
        return ""

    return build_context_from_rag_result(resultados[0])



def main():

    # MÉTRICAS — usando modelo por default (OpenAI)
    metrics = [
        AnswerRelevancyMetric(model="gpt-4.1-nano",async_mode=False),
        ContextualRelevancyMetric(model="gpt-4.1-nano",async_mode=False),
        FaithfulnessMetric(model="gpt-4.1-nano",async_mode=False),
    ]

    test_cases_llm: List[LLMTestCase] = []

    # Construir todos los casos
    for case in TEST_CASES:
        query = case["query"]
        categoria = case["categoria"]
        subcategoria = case["subcategoria"]
        expected_answer = case["expected"]

        context = run_rag(query, categoria, subcategoria)
       
        context_list = [context] if context else []

        tc = LLMTestCase(
            input=query,
            actual_output=context,
            expected_output=expected_answer,
            context=context_list,
            retrieval_context=context_list,
            name=case["name"],
        )
        test_cases_llm.append(tc)

    # Ejecutar evaluación
    report = evaluate(test_cases_llm, metrics=metrics)    

if __name__ == "__main__":
    main()
