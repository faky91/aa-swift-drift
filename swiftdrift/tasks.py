"""
Celery tasks.

The task delete_expired_wormholes removes expired entries.
It is executed periodically via Celery Beat; the schedule entry
goes into local.py (see README).
"""

import logging

from celery import shared_task
from django.utils import timezone

from .models import DrifterWormhole

logger = logging.getLogger(__name__)


@shared_task
def delete_expired_wormholes():
    """Delete all wormhole entries whose expiry date has been reached."""
    deleted_count, _ = DrifterWormhole.objects.filter(
        expires_at__lte=timezone.now()
    ).delete()
    if deleted_count:
        logger.info("Swift Drift: deleted %d expired wormholes", deleted_count)
    return deleted_count
