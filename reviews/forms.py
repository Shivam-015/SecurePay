from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {
            'rating': forms.Select(attrs={'class': 'review-rating'}),
            'comment': forms.Textarea(attrs={'rows': 4, 'maxlength': 2000, 'placeholder': 'Describe what working together was like.'}),
        }

    def clean_comment(self):
        return self.cleaned_data.get('comment', '').strip()
