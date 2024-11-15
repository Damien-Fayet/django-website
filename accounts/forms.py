from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import User

        
class UserRegisterForm(UserCreationForm):

    username = forms.CharField( 
        label = 'Nom',
        required = True,
    )
class Meta:
    model = User
    fields = ['username',  'password1', 'password2']