"""Keep a StaffProfile alongside every user account."""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StaffProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="create_staff_profile")
def create_staff_profile(sender, instance, created, **kwargs):
    """A new login always gets a profile, so role lookups never crash."""
    if created:
        StaffProfile.objects.get_or_create(user=instance)
