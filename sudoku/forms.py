from django import forms

class SudokuSizeForm(forms.Form):
    
    
    def __init__(self, *args, **kwargs):
        super(SudokuSizeForm, self).__init__(*args, **kwargs)
        for i in range(int(4)):
            self.fields[f'image{i+1}'] = forms.ImageField(label=f'Image {i+1}', required=False)

