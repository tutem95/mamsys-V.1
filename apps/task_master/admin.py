from django.contrib import admin

from .models import Mix, MixComponent, Task, TaskAdjustmentSuggestion, TaskComponent


class MixComponentInline(admin.TabularInline):
    model = MixComponent
    extra = 0
    fk_name = "mix"
    autocomplete_fields = ("material", "sub_mix", "input_unit")


@admin.register(Mix)
class MixAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "output_unit", "version", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")
    autocomplete_fields = ("output_unit",)
    inlines = [MixComponentInline]


class TaskComponentInline(admin.TabularInline):
    model = TaskComponent
    extra = 0
    fk_name = "task"
    autocomplete_fields = (
        "material", "position", "subcontract", "sub_mix", "sub_task", "input_unit",
    )
    fields = ("source_type", "material", "position", "subcontract", "sub_mix", "sub_task",
              "quantity_per_unit", "input_unit", "classification", "detail")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "rubro", "subrubro", "output_unit", "version", "active")
    list_filter = ("active", "rubro")
    search_fields = ("name", "code")
    autocomplete_fields = ("rubro", "subrubro", "output_unit")
    inlines = [TaskComponentInline]


@admin.register(MixComponent)
class MixComponentAdmin(admin.ModelAdmin):
    list_display = ("mix", "material", "sub_mix", "quantity_per_unit", "input_unit")
    autocomplete_fields = ("mix", "material", "sub_mix", "input_unit")


@admin.register(TaskComponent)
class TaskComponentAdmin(admin.ModelAdmin):
    list_display = ("task", "source_type", "quantity_per_unit", "input_unit", "classification")
    list_filter = ("source_type", "classification")
    search_fields = ("task__name", "task__code", "detail")
    autocomplete_fields = ("task", "material", "position", "subcontract", "sub_mix", "sub_task", "input_unit")


@admin.register(TaskAdjustmentSuggestion)
class TaskAdjustmentSuggestionAdmin(admin.ModelAdmin):
    list_display = ("task", "current_quantity", "suggested_quantity", "variance_pct", "status")
    list_filter = ("status",)
    autocomplete_fields = ("task", "component")
