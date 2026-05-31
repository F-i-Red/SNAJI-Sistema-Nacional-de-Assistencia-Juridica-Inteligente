
from pydantic import BaseModel
from typing import List, Dict

class ProcessState(BaseModel):
    process_id: str
    area_juridica: str
    factos_confirmados: List[str] = []
    factos_contestados: List[str] = []
    normas_aplicadas: List[str] = []
    contraditorio: List[str] = []
    riscos: List[str] = []
    auditoria: Dict = {}
