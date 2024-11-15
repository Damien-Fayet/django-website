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
    success_url = reverse_lazy("home")
    template_name = "registration/signup.html"
    
    def form_valid(self, form):
        valid = super(SignUpView, self).form_valid(form)
        password = form.cleaned_data.get('password1')
        #user = authenticate( password=password)
        user = form.save()
        login(self.request, user)
        return valid