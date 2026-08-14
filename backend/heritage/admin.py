from django.contrib import admin
from .models import Founder


@admin.register(Founder)
class FounderAdmin(admin.ModelAdmin):

    list_display = (
        "founder_code",
        "founder_name",
        "spiritual_name",
    )

    search_fields = (
        "founder_code",
        "founder_name",
        "spiritual_name",
    )