from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Domain, Invitation, Membership, Organization


@admin.register(Organization)
class OrganizationAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "tax_id", "is_active", "created_at")
    list_filter = ("is_active", "country")
    search_fields = ("name", "slug", "tax_id")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active", "accepted_at")
    list_filter = ("is_active", "organization", "role")
    search_fields = ("user__email", "organization__name")
    autocomplete_fields = ("user", "organization", "role")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "expires_at", "accepted_at")
    list_filter = ("organization", "role")
    search_fields = ("email",)
