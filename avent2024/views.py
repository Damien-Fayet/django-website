from django.shortcuts import render, redirect
from .forms import SudokuSizeForm
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User

def home(request):
    
    return render(request, 'avent2024/home.html', {})
    form = SudokuSizeForm()
    return render(request, 'sudoku/home.html', {'form': form})

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
