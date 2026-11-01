from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=70, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.CharField(max_length=220, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Gig(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'

    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gigs',
        limit_choices_to={'role': 'freelancer'},
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='gigs')
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(max_length=4000)
    starting_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    currency = models.CharField(
        max_length=3,
        default='INR',
        validators=[RegexValidator(r'^[A-Z]{3}$', 'Use a three-letter uppercase currency code.')],
    )
    delivery_days = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('status', 'category', 'starting_price'), name='gig_search_idx'),
            models.Index(fields=('freelancer', 'status'), name='gig_owner_status_idx'),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(starting_price__gt=0), name='gig_price_positive'),
            models.CheckConstraint(condition=models.Q(delivery_days__gt=0), name='gig_delivery_positive'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:110] or 'service'
            candidate = base_slug
            suffix = 2
            while Gig.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base_slug[:110]}-{suffix}'
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
