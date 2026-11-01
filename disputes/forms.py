from django import forms

from .models import Dispute, DisputeMessage


class DisputeOpenForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ('reason', 'description')
        widgets = {'description': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Describe the issue, what you have tried, and the outcome you are seeking.'})}

    def clean_description(self):
        return self.cleaned_data['description'].strip()


class DisputeMessageForm(forms.ModelForm):
    class Meta:
        model = DisputeMessage
        fields = ('body',)
        widgets = {'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add relevant context for the other participant and staff reviewer.'})}

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Write an update before sending.')
        return body


class DisputeResolutionForm(forms.Form):
    outcome = forms.ChoiceField(choices=Dispute.Outcome.choices)
    resolution_note = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Summarize the staff decision.'}))
