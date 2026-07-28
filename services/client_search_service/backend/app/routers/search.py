from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..db import get_db
from ..models import Client
from ..schemas import ClientResult, SearchResponse

router = APIRouter(prefix="/api", tags=["search"], dependencies=[Depends(require_staff)])


@router.get("/search", response_model=SearchResponse)
def search(q: str = "", db: Session = Depends(get_db)):
    """Соответствует payments/views.py:client_search_view — тот же регистронезависимый поиск
    подстроки по имени/фамилии/отчеству/bitrix_id, выполненный через ILIKE вместо Python-цикла."""
    term = q.strip()

    query = db.query(Client)
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(
                Client.name.ilike(like),
                Client.surname.ilike(like),
                Client.middlename.ilike(like),
                Client.bitrix_id.ilike(like),
            )
        )
    else:
        query = query.order_by(Client.surname, Client.name)

    clients = query.all()

    results = [
        ClientResult(
            id=c.id,
            name=c.name,
            surname=c.surname,
            middlename=c.middlename,
            bitrix_id=c.bitrix_id,
            stage_name=c.stage.name if c.stage else None,
        )
        for c in clients
    ]
    return SearchResponse(query=term, results=results)
