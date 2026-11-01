from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from .models import Contract, Milestone
from .models import Submission


class ContractProposalForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ('title', 'scope', 'terms')
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'A short name for this project'}),
            'scope': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Describe the work, expected outcome, and what is included.'}),
            'terms': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Optional: payment notes, revision limits, or other agreed terms.'}),
        }


class MilestonePlanForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ('title', 'description', 'amount', 'due_date')
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. First draft'}),
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'What will be delivered at this stage?'}),
            'amount': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01', 'placeholder': 'Amount'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_due_date(self):
        due_date = self.cleaned_data['due_date']
        if due_date < timezone.localdate():
            raise ValidationError('A milestone due date cannot be in the past.')
        return due_date


class BaseMilestonePlanFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        amounts = [
            form.cleaned_data['amount']
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
        ]
        total = sum(amounts, Decimal('0.00'))
        if amounts and total <= 0:
            raise ValidationError('The milestone plan must have a positive total.')
        if total > Decimal('999999999.99'):
            raise ValidationError('The milestone total is above the supported contract amount.')
        dates = [
            form.cleaned_data['due_date']
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
        ]
        if dates != sorted(dates):
            raise ValidationError('Milestone target dates must stay in the same order as the plan.')

    def save(self, commit=True):
        self._next_sequence = 1
        return super().save(commit=commit)

    def save_new(self, form, commit=True):
        instance = super().save_new(form, commit=False)
        instance.sequence = self._next_sequence
        self._next_sequence += 1
        if commit:
            instance.save()
        return instance


MilestonePlanFormSet = inlineformset_factory(
    Contract,
    Milestone,
    form=MilestonePlanForm,
    formset=BaseMilestonePlanFormSet,
    extra=1,
    min_num=1,
    max_num=8,
    validate_min=True,
    validate_max=True,
    can_delete=False,
)


class ContractResponseForm(forms.Form):
    note = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={
        'rows': 3,
        'placeholder': 'Optional note to the other person',
    }))


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ('kind', 'content', 'url', 'file')
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Describe the work completed or add delivery notes.'}),
            'url': forms.URLInput(attrs={'placeholder': 'https://…'}),
            'file': forms.ClearableFileInput(),
        }

    def clean(self):
        data = super().clean()
        kind = data.get('kind')
        if kind == Submission.Kind.TEXT and not data.get('content', '').strip():
            self.add_error('content', 'Add a written update before submitting.')
        elif kind == Submission.Kind.LINK and not data.get('url'):
            self.add_error('url', 'Add the link to your delivery.')
        elif kind == Submission.Kind.FILE and not data.get('file'):
            self.add_error('file', 'Choose a delivery file.')
        upload = data.get('file')
        if upload:
            allowed = {'.pdf', '.docx', '.png', '.jpg', '.jpeg', '.zip', '.mp4', '.webm'}
            from pathlib import Path
            if Path(upload.name).suffix.lower() not in allowed:
                self.add_error('file', 'Use a PDF, DOCX, image, ZIP, MP4, or WebM file.')
            if upload.size > 25 * 1024 * 1024:
                self.add_error('file', 'Files must be 25 MB or smaller.')
        return data


class RevisionForm(forms.Form):
    note = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={
        'rows': 3, 'placeholder': 'Explain what needs to change.',
    }))
