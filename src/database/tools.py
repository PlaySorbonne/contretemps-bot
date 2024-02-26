
from sqlalchemy import select, inspect

def get_or_create(session, table, defaults=None, **ident):
    obj = session.get(table, ident)
    if obj is not None:
        return obj
    if defaults:
        ident.update(defaults)
    obj = table(**ident)
    session.add(obj)
    return obj

def detached_copy(obj):
    cls = type(obj)
    attributes = inspect(cls).c.keys()
    return cls(**{a:obj.__dict__[a] for a in attributes})
