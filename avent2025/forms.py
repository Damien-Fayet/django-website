from django import forms
from django.core.validators import EmailValidator


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        required=True,
        label="Votre nom",
        widget=forms.TextInput(attrs={
            'placeholder': 'Entrez votre nom',
            'class': 'contact-input'
        })
    )
    
    email = forms.EmailField(
        required=True,
        label="Votre email",
        validators=[EmailValidator()],
        widget=forms.EmailInput(attrs={
            'placeholder': 'votre@email.com',
            'class': 'contact-input'
        })
    )
    
    subject = forms.CharField(
        max_length=200,
        required=True,
        label="Sujet",
        widget=forms.TextInput(attrs={
            'placeholder': 'Sujet de votre message',
            'class': 'contact-input'
        })
    )
    
    message = forms.CharField(
        required=True,
        label="Message",
        widget=forms.Textarea(attrs={
            'placeholder': 'Écrivez votre message ici...',
            'class': 'contact-textarea',
            'rows': 6
        })
    )
    
    def clean_message(self):
        message = self.cleaned_data.get('message')
        if len(message) < 10:
            raise forms.ValidationError("Votre message doit contenir au moins 10 caractères.")
        return message


class SudokuSizeForm(forms.Form):
    SIZE_CHOICES = [
        (4, '4x4'),
        (9, '9x9'),
    ]
    size = forms.ChoiceField(choices=SIZE_CHOICES, label='Taille du Sudoku', initial=4)
    def __init__(self, *args, **kwargs):
        size = kwargs.pop('size', None)
        super(SudokuSizeForm, self).__init__(*args, **kwargs)
        if size:
            for i in range(int(size)):
                self.fields[f'image{i+1}'] = forms.ImageField(label=f'Image {i+1}', required=False)


