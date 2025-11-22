from typing import Any, Text, Dict, List, Optional
import re

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict


# ==== "Base de datos" de empleados (simulada) ====
# Más adelante esto se puede sustituir por consulta real a una BD.
EMPLOYEE_DB = {
    "E12345": {"name": "Juan Pérez", "branch": "3182"},
    "E54321": {"name": "María López", "branch": "1201"},
    "E00001": {"name": "Empleado Demo", "branch": "9999"},
}


def extract_employee_code_from_message(tracker: Tracker) -> Optional[str]:
    """Simulación del proceso de OCR.
    Por ahora extraemos el código desde el texto del mensaje.
    Más adelante, aquí conectaremos el resultado del OCR sobre la imagen del carnet.
    """

    text = tracker.latest_message.get("text") or ""

    # Buscamos patrones tipo E12345 o solo 5 dígitos
    match = re.search(r"(E\d{5})", text.upper())
    if match:
        return match.group(1)

    # Si no viene con 'E', probamos solo dígitos (ej. 12345)
    match = re.search(r"\b(\d{5})\b", text)
    if match:
        return "E" + match.group(1)

    return None


class ActionHelloWorld(Action):
    def name(self) -> Text:
        return "action_hello_world"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="¡Hola desde la acción personalizada!")
        return []


class ActionVerificarIdentidad(Action):
    """Verificación de identidad a partir del carnet (simulado).
    - Extrae el código de empleado (por ahora, del texto)
    - Valida contra EMPLOYEE_DB
    - Si es válido, setea slots y marca authenticated=True
    - Si no, informa y NO autentica.
    """

    def name(self) -> Text:
        return "action_verificar_identidad"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Si ya está autenticado, no repetimos
        if tracker.get_slot("authenticated"):
            dispatcher.utter_message(
                text="Ya he validado tu identidad previamente ✅. Podemos continuar."
            )
            return []

        employee_code = extract_employee_code_from_message(tracker)

        if not employee_code:
            dispatcher.utter_message(
                text=(
                    "No pude identificar tu código de empleado a partir del mensaje.\n"
                    "Por favor, envíame tu código de empleado en el formato E12345 "
                    "o 5 dígitos, por ejemplo: 12345."
                )
            )
            # No seteamos authenticated, el flujo no deberá continuar
            return []

        empleado = EMPLOYEE_DB.get(employee_code)
        if not empleado:
            dispatcher.utter_message(
                text=(
                    f"No encontré el código de empleado {employee_code} en la base de datos.\n"
                    "Verifica tu carnet o contacta a soporte para revisar tus datos."
                )
            )
            # Autenticación fallida
            return [
                SlotSet("authenticated", False),
                SlotSet("employee_code", None),
                SlotSet("employee_name", None),
                SlotSet("branch_number", None),
            ]

        employee_name = empleado["name"]
        branch_number = empleado["branch"]

        dispatcher.utter_message(
            text=(
                "Perfecto, he validado tu identidad ✅.\n\n"
                f"👤 Empleado: {employee_name} (código {employee_code})\n"
                f"📍 Sucursal: {branch_number}\n\n"
                "Ahora vamos a registrar tu incidente."
            )
        )

        return [
            SlotSet("authenticated", True),
            SlotSet("employee_code", employee_code),
            SlotSet("employee_name", employee_name),
            SlotSet("branch_number", branch_number),
        ]


class ActionConfirmarReporte(Action):
    """Acción que se ejecuta al finalizar el formulario de incidente.
    Resume la información y genera un ID de ticket simple.
    """

    def name(self) -> Text:
        return "action_confirmar_reporte"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        employee_name = tracker.get_slot("employee_name") or "No especificado"
        employee_code = tracker.get_slot("employee_code") or "No especificado"
        branch_number = tracker.get_slot("branch_number") or "No especificada"

        categoria = tracker.get_slot("categoria") or "No especificada"
        subcategoria = tracker.get_slot("subcategoria") or "No especificada"
        descripcion = tracker.get_slot("descripcion") or "Sin descripción"

        # Generar ticket simple (por ahora estático, luego lo haremos incremental o con DB)
        ticket_id = "INC000001"

        mensaje = (
            "He registrado tu incidente con la siguiente información:\n\n"
            f"📍 Sucursal: {branch_number}\n"
            f"👤 Empleado: {employee_name} (código {employee_code})\n"
            f"📂 Categoría: {categoria}\n"
            f"📦 Subcategoría: {subcategoria}\n"
            f"📝 Descripción: {descripcion}\n"
            f"🎫 Número de ticket: {ticket_id}\n\n"
            "Un ingeniero de soporte técnico dará seguimiento lo antes posible."
        )

        dispatcher.utter_message(text=mensaje)

        return [SlotSet("ticket_id", ticket_id)]


class ValidateIncidenteForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_incidente_form"

    async def required_slots(
        self,
        slots_mapped_in_domain: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        """Permite decidir dinámicamente qué slots pide el formulario."""

        categoria = tracker.get_slot("categoria")
        required = list(slots_mapped_in_domain)

        # Normalizamos la categoría a minúsculas para comparar
        cat_norm = (categoria or "").lower()

        # Solo pedimos subcategoria si la categoría es scanner o periférico
        # ya sea que venga como "scanner", "digitalizadora / scanner",
        # "periféricos", "periféricos / dispositivos", etc.        
        es_periferico = "perifer" in cat_norm  # captura "periférico", "perifericos", etc.

        if not (es_periferico):
            if "subcategoria" in required:
                required.remove("subcategoria")

        return required

    
class ActionStartNuevoIncidente(Action):
    def name(self) -> Text:
        return "action_start_nuevo_incidente"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Limpiamos TODOS los datos de autenticación e incidente
        events: List[Dict[Text, Any]] = [
            SlotSet("authenticated", False),
            SlotSet("employee_code", None),
            SlotSet("employee_name", None),
            SlotSet("branch_number", None),
            SlotSet("categoria", None),
            SlotSet("subcategoria", None),
            SlotSet("descripcion", None),
            SlotSet("ticket_id", None),
        ]

        # Mensaje para el usuario
        dispatcher.utter_message(
            text=(
                "Perfecto 👍. Vamos a iniciar un nuevo reporte.\n\n"
                "Primero necesito validar tu identidad nuevamente.\n"
                "Por favor, envíame una foto de tu carnet corporativo o tu código de empleado."
            )
        )

        return events
