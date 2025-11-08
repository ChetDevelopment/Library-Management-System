from django import forms
from .models import UserRegister, Book

# --- Registration Form ---
class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}))

    class Meta:
        model = UserRegister
        fields = ['name', 'email', 'id_card', 'password', 'confirm_password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


# --- Login Form ---
class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Enter email'}))
    id_card = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'Enter ID card'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}))


# --- Admin Login Form ---
class AdminLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Admin email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))


# --- Edit Profile Form ---
class EditProfileForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'New Password (optional)'}),
        required=False
    )
    avatar = forms.ImageField(required=False)

    class Meta:
        model = UserRegister
        fields = ['name', 'email', 'id_card', 'password', 'avatar']


# --- Add Book Form ---
class AddBookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'category', 'isbn', 'status', 'copies']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Enter book title'}),
            'author': forms.TextInput(attrs={'placeholder': 'Enter author name'}),
            'isbn': forms.TextInput(attrs={'placeholder': 'Enter ISBN'}),
            'category': forms.TextInput(attrs={'placeholder': 'Enter category'}),
        }
