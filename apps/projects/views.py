from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.permissions.constants import VIEW_PROJECTS
from apps.permissions.decorators import PermissionRequiredMixin

from .forms import ProjectForm
from .models import Project


@method_decorator(login_required, name="dispatch")
class ProjectListView(PermissionRequiredMixin, ListView):
    required_permission = VIEW_PROJECTS
    model = Project
    template_name = "projects/list.html"
    paginate_by = 50
    context_object_name = "projects"

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("company", "status", "project_manager")
        )
        show_archived = self.request.GET.get("archivadas") == "1"
        if not show_archived:
            qs = qs.filter(is_archived=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["show_archived"] = self.request.GET.get("archivadas") == "1"
        return ctx


@method_decorator(login_required, name="dispatch")
class ProjectDetailView(DetailView):
    model = Project
    template_name = "projects/detail.html"
    context_object_name = "project"


@method_decorator(login_required, name="dispatch")
class ProjectCreateView(CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/form.html"

    def get_success_url(self):
        return reverse_lazy("projects:detail", args=[self.object.pk])

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class ProjectUpdateView(UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/form.html"

    def get_success_url(self):
        return reverse_lazy("projects:detail", args=[self.object.pk])

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)
