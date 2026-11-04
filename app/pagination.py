from fastapi import Query, Response


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def pagination_params(
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
) -> tuple[int, int]:
    return limit, offset


def paginate_query(query, *, order_by, limit: int, offset: int):
    total = query.order_by(None).count()
    items = query.order_by(order_by).offset(offset).limit(limit).all()
    return items, total


def set_total_count(response: Response, total: int) -> None:
    response.headers["X-Total-Count"] = str(total)
