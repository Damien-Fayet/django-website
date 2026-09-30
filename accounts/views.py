# accounts/views.py
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from .forms import UserRegisterForm

class SignUpView(CreateView):
    form_class = UserRegisterForm
    success_url = reverse_lazy("avent2026:home")  # Redirige vers le calendrier après inscription
    template_name = "registration/modern_signup.html"
    
    def form_valid(self, form):
        valid = super(SignUpView, self).form_valid(form)
        password = form.cleaned_data.get('password1')
        user = form.save()
        login(self.request, user)
        return valid

def public_home(request):
    """Page d'accueil publique ; redirige vers le calendrier si connecté."""
    if request.user.is_authenticated:
        return redirect('avent2026:home')
    return render(request, 'modern_welcome.html')
