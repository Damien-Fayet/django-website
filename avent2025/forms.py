from django import forms

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

