from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    contract = models.ForeignKey('contracts.Contract', on_delete=models.PROTECT, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='written_reviews')
    reviewee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='received_reviews')
    rating = models.PositiveSmallIntegerField(
        choices=((1, '1 · Needs improvement'), (2, '2 · Fair'), (3, '3 · Good'), (4, '4 · Very good'), (5, '5 · Excellent')),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('contract', 'reviewer'), name='review_contract_reviewer_unique'),
            models.CheckConstraint(condition=~models.Q(reviewer=models.F('reviewee')), name='review_parties_differ'),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_range'),
        ]

    def __str__(self):
        return f'{self.rating}/5 · {self.contract.title}'
