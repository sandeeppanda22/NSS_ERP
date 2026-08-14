import uuid
from django.db import models
from django.core.exceptions import ValidationError


class Founder(models.Model):
    """
    Frozen NSS Founder Master

    Only one record shall exist:
    Swami Nigamananda Paramahansa Dev
    """

    founder_pk = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    founder_code = models.CharField(
        max_length=20,
        unique=True
    )

    founder_name = models.CharField(
        max_length=200
    )

    spiritual_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    birth_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    father_name = models.CharField(
    max_length=200,
    blank=True,
    null=True
    )

    mother_name = models.CharField(
    max_length=200,
    blank=True,
    null=True
    )
    
    birth_date = models.DateField(
        blank=True,
        null=True
    )

    mahasamadhi_date = models.DateField(
        blank=True,
        null=True
    )

    birth_place = models.CharField(
        max_length=300,
        blank=True,
        null=True
    )

    biography = models.TextField(
        blank=True,
        null=True
    )

    founder_message = models.TextField(
        blank=True,
        null=True
    )

    website_url = models.URLField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "founder_master"
        verbose_name = "Founder"
        verbose_name_plural = "Founder"

    def save(self, *args, **kwargs):

        if not self.pk and Founder.objects.exists():
            raise ValidationError(
                "Only one founder record is allowed."
            )

        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Founder record cannot be deleted."
    )

    def __str__(self):
        return self.founder_name