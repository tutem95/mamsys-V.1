from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from .forms import (
    MixComponentFormSet,
    MixForm,
    TaskComponentFormSet,
    TaskForm,
)
from .models import Mix, Task
from .services import TaskCostCalculator


# ---------------------------------------------------------------------------
# Mix
# ---------------------------------------------------------------------------


@method_decorator(login_required, name="dispatch")
class MixListView(ListView):
    model = Mix
    template_name = "task_master/mix_list.html"
    paginate_by = 50
    context_object_name = "mixes"

    def get_queryset(self):
        qs = super().get_queryset().select_related("output_unit")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_q"] = self.request.GET.get("q", "")
        return ctx


@login_required
def mix_create(request):
    return _mix_form(request, instance=None)


@login_required
def mix_edit(request, pk: int):
    return _mix_form(request, instance=get_object_or_404(Mix, pk=pk))


def _mix_form(request, instance: Mix | None):
    if request.method == "POST":
        form = MixForm(request.POST, instance=instance)
        formset = MixComponentFormSet(request.POST, instance=instance or Mix())
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    mix = form.save(commit=False)
                    if instance is None:
                        mix.created_by = request.user
                    mix.updated_by = request.user
                    mix.save()
                    formset.instance = mix
                    items = formset.save(commit=False)
                    for obj in formset.deleted_objects:
                        obj.delete()
                    for item in items:
                        item.full_clean()  # dispara detección de ciclos
                        item.save()
                messages.success(request, "Mezcla guardada.")
                return redirect("task_master:mix_detail", pk=mix.pk)
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
    else:
        form = MixForm(instance=instance)
        formset = MixComponentFormSet(instance=instance or Mix())
    return render(request, "task_master/mix_form.html", {
        "form": form, "formset": formset, "mix": instance,
    })


@login_required
def mix_detail(request, pk: int):
    mix = get_object_or_404(
        Mix.objects.select_related("output_unit").prefetch_related(
            "components__material", "components__sub_mix", "components__input_unit",
        ),
        pk=pk,
    )
    breakdown = TaskCostCalculator.calculate(mix)
    return render(request, "task_master/mix_detail.html", {
        "mix": mix, "breakdown": breakdown,
    })


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@method_decorator(login_required, name="dispatch")
class TaskListView(ListView):
    model = Task
    template_name = "task_master/task_list.html"
    paginate_by = 50
    context_object_name = "tasks"

    def get_queryset(self):
        qs = super().get_queryset().select_related("rubro", "subrubro", "output_unit")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        rubro = self.request.GET.get("rubro")
        if rubro:
            qs = qs.filter(rubro_id=rubro)
        return qs

    def get_context_data(self, **kwargs):
        from apps.catalog.models import Rubro
        ctx = super().get_context_data(**kwargs)
        ctx["current_q"] = self.request.GET.get("q", "")
        ctx["current_rubro"] = self.request.GET.get("rubro", "")
        ctx["rubros"] = Rubro.objects.filter(active=True).order_by("name")
        return ctx


@login_required
def task_create(request):
    return _task_form(request, instance=None)


@login_required
def task_edit(request, pk: int):
    return _task_form(request, instance=get_object_or_404(Task, pk=pk))


def _task_form(request, instance: Task | None):
    if request.method == "POST":
        form = TaskForm(request.POST, instance=instance)
        formset = TaskComponentFormSet(request.POST, instance=instance or Task())
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    task = form.save(commit=False)
                    if instance is None:
                        task.created_by = request.user
                    task.updated_by = request.user
                    task.save()
                    formset.instance = task
                    items = formset.save(commit=False)
                    for obj in formset.deleted_objects:
                        obj.delete()
                    for item in items:
                        item.full_clean()
                        item.save()
                messages.success(request, "Tarea guardada.")
                return redirect("task_master:task_detail", pk=task.pk)
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
    else:
        form = TaskForm(instance=instance)
        formset = TaskComponentFormSet(instance=instance or Task())
    return render(request, "task_master/task_form.html", {
        "form": form, "formset": formset, "task": instance,
    })


@login_required
def task_detail(request, pk: int):
    task = get_object_or_404(
        Task.objects.select_related("rubro", "subrubro", "output_unit").prefetch_related(
            "components__material", "components__position", "components__subcontract",
            "components__sub_mix", "components__sub_task", "components__input_unit",
        ),
        pk=pk,
    )
    breakdown = TaskCostCalculator.calculate(task)
    return render(request, "task_master/task_detail.html", {
        "task": task, "breakdown": breakdown,
    })


@login_required
def master_index(request):
    """Landing de la sección Maestros con accesos a Tareas y Mezclas."""
    return render(request, "task_master/index.html", {
        "tasks_count": Task.objects.filter(active=True).count(),
        "mixes_count": Mix.objects.filter(active=True).count(),
    })
