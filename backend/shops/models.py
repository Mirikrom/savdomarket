from django.db import models

from core.models import SoftDeleteModel, TimeStampedModel


class Organization(TimeStampedModel, SoftDeleteModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Branch(TimeStampedModel, SoftDeleteModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="branches"
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    is_main = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uniq_branch_name_per_organization"
            )
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.name}"
