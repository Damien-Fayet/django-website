from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Enigme, UserProfile
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from avent2024.models import UserProfile

# class UserForm(forms.ModelForm):
#     class Meta:
#         model = User
#         fields = ("first_name", "last_name")

# class UserProfileForm(forms.ModelForm):
#     class Meta:
#         model = UserProfile
#         fields = ("currentEnigma",)
        
@login_required
def home(request):
    if not hasattr(request.user, 'userprofile'):
        UserProfile.objects.create(user=request.user)
    
    current_enigma = request.user.userprofile.currentEnigma
    #if current_enigma == 0:
    return render(request, 'avent2024/home.html', {"current_enigma": current_enigma})
    return render(request, 'avent2024/enigme.html', {"current_enigma": current_enigma})

@login_required
def start_adventure(request):
    # Mettre à jour la valeur de currentEnigma à 1
    user_profile = request.user.userprofile
    user_profile.currentEnigma = 1
    user_profile.save()
    current_enigma = get_object_or_404(Enigme, id=request.user.userprofile.currentEnigma)
    #return redirect('avent2024:display_enigme')
    return render(request, 'avent2024/enigme.html',  {
            'reponse_enigme' : current_enigma.reponse,
            'enigme' : current_enigma,
            'user_reponse' : ''
        })

@login_required
def display_enigme(request,reponse=None):
    if request.user.userprofile.currentEnigma==0:
        return render(request, 'avent2024/enigme.html',  {
            'reponse_enigme' : current_enigma.reponse,
            'enigme' : current_enigma,
            'user_reponse' : reponse
        })
    current_enigma = get_object_or_404(Enigme, id=request.user.userprofile.currentEnigma)
    
    return render(request, 'avent2024/enigme.html',  {
        'reponse_enigme' : current_enigma.reponse,
        'enigme' : current_enigma,
        'user_reponse' : reponse
    })
    
@login_required
def error_enigme(request):
    current_enigma = get_object_or_404(Enigme, id=request.user.userprofile.currentEnigma)
    
    return render(request, 'avent2024/enigme.html',  {
        'reponse_enigme' : current_enigma.reponse,
        'enigme' : current_enigma,
        'user_reponse' : 'KO'
    })

@login_required
def validate_enigme(request):
    if request.method == "POST":
        user_profile = request.user.userprofile
        current_enigma_number = user_profile.currentEnigma
        current_enigma = get_object_or_404(Enigme, id=current_enigma_number)
        reponse = request.POST.get("reponse")

        if reponse == current_enigma.reponse:
            messages.success(request, "Bonne reponse")
            user_profile.currentEnigma += 1
            current_enigma = get_object_or_404(Enigme, id=user_profile.currentEnigma)
            user_profile.save()
            return render(request, 'avent2024/enigme.html',  {
                'reponse_enigme' : current_enigma.reponse,
                'enigme' : current_enigma,
                'user_reponse' : 'OK',
                'old_enigme_id' : current_enigma.id -1
            })
        else:
            return render(request, 'avent2024/enigme.html',  {
                'reponse_enigme' : current_enigma.reponse,
                'enigme' : current_enigma,
                'user_reponse' : 'KO'
            })

    return redirect('avent2024:display_enigme')

def register(request):
    if request.method == 'POST':
        username1 = request.POST['username']
        email1 = request.POST['email']
        password = request.POST['password']
        password1 = request.POST['password1']
        if password== password1:
            if User.objects.filter(email = email1).exists():
                messages.info(request,'Email already exists')
                return redirect('register')
            elif User.objects.filter(username = username1).exists():
                messages.info(request,'Username already exists')
                return redirect('register')
            else:
                user= User.objects.create_user(username=username1,email=email1,password=password)
                user.save()
            return redirect('login')
        else:
            messages.info(request,'Password not the same')
            return redirect('register')
    else:
        return render(request, 'avent2024/register.html')
