"""Detección de ciclos en recetas recursivas (Mix y Task).

DFS sobre el grafo de dependencias antes de guardar. Si la nueva referencia
crea un ciclo, validamos y bloqueamos.
"""

from __future__ import annotations


def detect_mix_cycle(parent_mix_id: int, candidate_sub_mix_id: int) -> bool:
    """¿Agregar candidate como sub_mix del parent crea un ciclo?

    True si candidate ya depende (directa o transitivamente) de parent.
    """
    from .models import MixComponent

    if parent_mix_id == candidate_sub_mix_id:
        return True

    visited: set[int] = set()
    stack: list[int] = [candidate_sub_mix_id]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        if current == parent_mix_id:
            return True
        deps = MixComponent.objects.filter(
            mix_id=current, sub_mix__isnull=False,
        ).values_list("sub_mix_id", flat=True)
        stack.extend(deps)
    return False


def detect_task_cycle(parent_task_id: int, candidate_sub_task_id: int) -> bool:
    """¿Agregar candidate como sub_task de parent crea un ciclo?"""
    from .models import TaskComponent

    if parent_task_id == candidate_sub_task_id:
        return True

    visited: set[int] = set()
    stack: list[int] = [candidate_sub_task_id]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        if current == parent_task_id:
            return True
        deps = TaskComponent.objects.filter(
            task_id=current, sub_task__isnull=False,
        ).values_list("sub_task_id", flat=True)
        stack.extend(deps)
    return False
