from django.shortcuts import render, redirect
from .forms import SudokuSizeForm
from django.core.files.storage import FileSystemStorage
from .sudoku import create_board
from django.conf import settings
import os

def home(request):
    if request.method == 'POST':
        size = 4
        difficulty = request.POST.get('difficulty')
        form = SudokuSizeForm(request.POST, request.FILES)
        if form.is_valid():
            images = []
            fs = FileSystemStorage(location=settings.MEDIA_ROOT)
            for i in range(1, int(size) + 1):
                image = request.FILES.get(f'image{i}')
                default_image = request.POST.get(f'default_image{i}')
                
                if image:
                    #print(f"Image {i} received: {image.name}")
                    filename = fs.save(f"image{i}", image)
                    image_url = settings.MEDIA_URL + filename
                    images.append(image_url)
                    #print(f"Image URL = {image_url}")
                elif default_image:
                    #print(f"Default image {i} URL used: {default_image}")
                    images.append(default_image)
                else:
                    print(f"Image {i} not received")
                    images.append(None)
            board = create_board(int(size), difficulty)
            return render(request, 'sudoku/grid.html', {'board': board, 'images': images})
        else:
            print("Form is not valid")
            print(form)
    else:
        form = SudokuSizeForm()
    return render(request, 'sudoku/home.html', {'form': form})