from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.db import connection
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import date, datetime, timedelta
from .models import UserRegister, Book, BorrowHistory, BorrowRequest, Notification, SystemSettings
from .forms import RegistrationForm, LoginForm, AdminLoginForm, EditProfileForm, AddBookForm


# ===================== HOME =====================
def home(request):
    return render(request, 'index.html')


# ===================== REGISTER =====================
def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.password = make_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, "Registration successful! Please log in.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})


# ===================== LOGIN =====================
def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            id_card = form.cleaned_data['id_card']
            password = form.cleaned_data['password']

            try:
                user = UserRegister.objects.get(email=email, id_card=id_card)
                if check_password(password, user.password):
                    request.session['user_id'] = user.id
                    request.session['user_name'] = user.name
                    messages.success(request, "Logged in successfully!")
                    return redirect('dashboard')
                else:
                    messages.error(request, "Invalid password.")
            except UserRegister.DoesNotExist:
                messages.error(request, "User not found.")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


# ===================== LOGOUT =====================
def logout(request):
    request.session.flush()
    messages.success(request, "Logged out successfully.")
    return redirect('login')


# ===================== DASHBOARD =====================
def dashboard(request):
    if 'user_id' not in request.session:
        messages.warning(request, "Please login first.")
        return redirect('login')

    user = get_object_or_404(UserRegister, pk=request.session['user_id'])
    total_books = Book.objects.count()
    available_books = Book.objects.filter(status='available').count()
    issued_books = Book.objects.filter(status='issued').count()
    overdue_books = BorrowHistory.objects.filter(return_date__isnull=True, due_date__lt=date.today()).count()
    total_members = UserRegister.objects.count()

    borrowed_books = BorrowHistory.objects.filter(user=user, return_date__isnull=True)
    borrow_history = BorrowHistory.objects.filter(user=user)
    notifications = Notification.objects.filter(user=user).order_by('-created_at')

    user_fines = sum(h.fine for h in borrow_history if h.fine > 0)

    return render(request, 'dashboard.html', {
        'user': user,
        'total_books': total_books,
        'available_books': available_books,
        'issued_books': issued_books,
        'total_members': total_members,
        'overdue_books': overdue_books,
        'borrowed_books': borrowed_books,
        'borrow_history': borrow_history,
        'notifications': notifications,
        'user_fines': user_fines,
    })


# ===================== PROFILE =====================
def view_profile(request):
    if 'user_id' not in request.session:
        messages.warning(request, "Please login first.")
        return redirect('login')

    user = get_object_or_404(UserRegister, pk=request.session['user_id'])
    return render(request, 'view_profile.html', {'user': user})


def edit_profile(request):
    if 'user_id' not in request.session:
        messages.warning(request, "Please login first.")
        return redirect('login')

    user = get_object_or_404(UserRegister, pk=request.session['user_id'])
    if request.method == 'POST':
        form = EditProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            updated_user = form.save(commit=False)
            if form.cleaned_data['password']:
                updated_user.password = make_password(form.cleaned_data['password'])
            updated_user.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('dashboard')
    else:
        form = EditProfileForm(instance=user)
    return render(request, 'edit_profile.html', {'form': form, 'user': user})


# ===================== BOOKS =====================
def books(request):
    if 'user_id' not in request.session:
        messages.warning(request, "Please login first.")
        return redirect('login')

    query = request.GET.get('query', '')
    if query:
        books = Book.objects.filter(title__icontains=query) | Book.objects.filter(author__icontains=query)
    else:
        books = Book.objects.all()

    return render(request, 'books.html', {'books': books, 'query': query})


def add_book(request):
    if 'admin_id' not in request.session:
        messages.warning(request, "Please login as admin.")
        return redirect('admin_login')

    if request.method == 'POST':
        form = AddBookForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Book added successfully!")
            return redirect('admin_dashboard')
    else:
        form = AddBookForm()
    return render(request, 'add_book.html', {'form': form})


# ===================== BORROW / RETURN =====================
def borrow_book(request, book_id):
    if 'user_id' not in request.session:
        messages.warning(request, "Please login first.")
        return redirect('login')

    book = get_object_or_404(Book, pk=book_id)
    user = get_object_or_404(UserRegister, pk=request.session['user_id'])

    if book.status != 'available':
        messages.warning(request, "Book not available for borrowing.")
        return redirect('books')

    if request.method == 'POST':
        borrow_date = date.today()
        due_date = borrow_date + timedelta(days=14)
        BorrowHistory.objects.create(
            user=user,
            book=book,
            borrow_date=borrow_date,
            due_date=due_date
        )
        book.status = 'issued'
        book.save()
        Notification.objects.create(user=user, message=f"You borrowed '{book.title}'.")
        messages.success(request, f"You borrowed '{book.title}' successfully!")
        return redirect('dashboard')

    return render(request, 'borrow_form.html', {'book': book})


def return_book(request, borrow_id):
    if 'user_id' not in request.session:
        return redirect('login')

    borrow = get_object_or_404(BorrowHistory, pk=borrow_id, user_id=request.session['user_id'])
    today = date.today()
    fine_per_day = 0.50
    days_late = max(0, (today - borrow.due_date).days)
    fine = days_late * fine_per_day

    if request.method == 'POST':
        borrow.return_date = today
        borrow.fine = fine
        borrow.save()
        borrow.book.status = 'available'
        borrow.book.save()
        Notification.objects.create(
            user=borrow.user,
            message=f"You returned '{borrow.book.title}'. Fine: ${fine:.2f}"
        )
        messages.success(request, f"Book returned successfully! Fine: ${fine:.2f}")
        return redirect('dashboard')

    return render(request, 'return_book.html', {
        'borrow': borrow,
        'fine': fine,
        'days_late': days_late,
    })


# ===================== NOTIFICATIONS =====================
def notifications(request):
    if 'user_id' not in request.session:
        messages.warning(request, "Please login first.")
        return redirect('login')

    user = get_object_or_404(UserRegister, pk=request.session['user_id'])
    notifications = Notification.objects.filter(user=user).order_by('-created_at')
    for note in notifications:
        if not note.seen:
            note.seen = True
            note.save()

    return render(request, 'notifications.html', {'notifications': notifications})


# ===================== ADMIN =====================
def admin_login(request):
    if request.method == 'POST':
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            try:
                admin = UserRegister.objects.get(email=email)
                if check_password(password, admin.password):
                    request.session['admin_id'] = admin.id
                    request.session['admin_name'] = admin.name
                    messages.success(request, "Admin login successful!")
                    return redirect('admin_dashboard')
                else:
                    messages.error(request, "Incorrect password.")
            except UserRegister.DoesNotExist:
                messages.error(request, "Admin not found.")
    else:
        form = AdminLoginForm()
    return render(request, 'admin_login.html', {'form': form})


def admin_dashboard(request):
    if 'admin_id' not in request.session:
        messages.warning(request, "Please login as admin.")
        return redirect('admin_login')

    total_books = Book.objects.count()
    available_books = Book.objects.filter(status='available').count()
    issued_books = Book.objects.filter(status='issued').count()
    total_members = UserRegister.objects.count()
    overdue_books = BorrowHistory.objects.filter(return_date__isnull=True, due_date__lt=date.today()).count()
    borrow_requests = BorrowRequest.objects.filter(status='Pending')

    return render(request, 'dashboard_admin.html', {
        'total_books': total_books,
        'available_books': available_books,
        'issued_books': issued_books,
        'total_members': total_members,
        'overdue_books': overdue_books,
        'requests': borrow_requests,
        'admin_name': request.session.get('admin_name')
    })


def admin_logout(request):
    request.session.flush()
    messages.success(request, "Admin logged out successfully.")
    return redirect('admin_login')
