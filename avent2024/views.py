import random
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Enigme, Indice, UserProfile
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
import unidecode

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
    return redirect('avent2024:display_enigme')
    # return render(request, 'avent2024/enigme.html',  {
    #         'reponse_enigme' : current_enigma.reponse,
    #         'enigme' : current_enigma,
    #         'user_reponse' : ''
    #     })

@login_required
def display_enigme(request,reponse=None):
    if request.user.userprofile.currentEnigma==0:
        return render(request, 'avent2024/enigme.html',  {
            'reponse_enigme' : current_enigma.reponse,
            'enigme' : current_enigma,
            'user_reponse' : reponse
        })
    
    current_enigma = get_object_or_404(Enigme, id=request.user.userprofile.currentEnigma)
    # Récupérer tous les indices de cette enigme
    indices = Indice.objects.filter(
        enigme=current_enigma
    )
    
    for i in indices:
        print(i)
    # Lister les indice revelés
    indice_reveles_list = []
    if request.user.userprofile.indices_enigme_reveles:
        indice_reveles_list = [int(x) for x in request.user.userprofile.indices_enigme_reveles.split(",")]
    
    print(f"liste numeros : {indice_reveles_list}")
    indices_reveles = indices.filter(id__in= indice_reveles_list)
    indices_hidden = indices.exclude(id__in=indice_reveles_list)
    return render(request, 'avent2024/enigme.html',  {
        'reponse_enigme' : current_enigma.reponse,
        'enigme' : current_enigma,
        'user_reponse' : reponse,
        'indices' : indices,
        'indices_reveles': indices_reveles,
        'indices_hidden': indices_hidden,
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
        clean_reponse = ''.join(reponse.split()).lower()
        clean_reponse = unidecode.unidecode(clean_reponse )
        if clean_reponse in current_enigma.reponse.split(","):
            messages.success(request, "Bonne reponse")
            user_profile.currentEnigma += 1
            current_enigma = get_object_or_404(Enigme, id=user_profile.currentEnigma)
            user_profile.save()
            image_id = random.randint(1, 6)
            return render(request, 'avent2024/enigme.html',  {
                'reponse_enigme' : current_enigma.reponse,
                'enigme' : current_enigma,
                'user_reponse' : 'OK',
                'old_enigme_id' : current_enigma.id -1,
                'image_reponse' : f"gagne{image_id}.gif"
            })
        else:
            image_id = random.randint(1, 24)
            return render(request, 'avent2024/enigme.html',  {
                'reponse_enigme' : current_enigma.reponse,
                'enigme' : current_enigma,
                'user_reponse' : 'KO',
                'image_reponse' : f"perdu{image_id}.gif"
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

@login_required
def reveler_indice(request):
    indice_id = int(request.POST.get("indice_id"))
    indice = get_object_or_404(Indice, id=indice_id)
    user_profile = request.user.userprofile
    print(f"Current list indices reveles : {user_profile.indices_enigme_reveles}")
    if len(user_profile.indices_enigme_reveles)>0:
        tmp_list = user_profile.indices_enigme_reveles.split(",")
    else: 
        tmp_list=[]
    tmp_list.append(str(indice.numero))
    print(f"new list indices reveles : {tmp_list}")
    user_profile.indices_enigme_reveles = ",".join(tmp_list)
        
    user_profile.save()
    
    return redirect('avent2024:display_enigme')