from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import User

        
class UserRegisterForm(UserCreationForm):
    username = forms.CharField( 
        label='Nom d\'utilisateur',
        required=True,
        help_text='Choisissez un nom unique pour vous identifier dans le calendrier.',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Votre nom d\'utilisateur'
        })
    )
    
    email = forms.EmailField(
        label='Email',
        required=False,
        help_text='Facultatif - Pour récupérer votre compte en cas d\'oubli de mot de passe.',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'votre.email@exemple.com (facultatif)'
        })
    )
    
    password1 = forms.CharField(
        label='Mot de passe',
        required=True,
        help_text='Minimum 8 caractères. Pas trop simple !',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Choisissez un mot de passe sécurisé'
        })
    )
    
    password2 = forms.CharField(
        label='Confirmation du mot de passe',
        required=True,
        help_text='Entrez le même mot de passe pour confirmation.',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirmez votre mot de passe'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        # Messages d'erreur personnalisés en français
        self.error_messages = {
            'password_mismatch': 'Les deux mots de passe ne correspondent pas.',
        }