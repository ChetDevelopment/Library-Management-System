from django.db import models
from django.contrib.auth.models import User

# User Table (same as user_register)
class UserRegister(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    id_card = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=255)
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True, null=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return self.name


# Book Table
class Book(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('issued', 'Issued'),
        ('reserved', 'Reserved'),
    ]
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    category = models.CharField(max_length=100, blank=True, null=True)
    isbn = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    copies = models.IntegerField(default=1)
    due_date = models.DateField(blank=True, null=True)
    reserved_by_user = models.ForeignKey(UserRegister, on_delete=models.SET_NULL, null=True, blank=True, related_name='reserved_books')

    def __str__(self):
        return self.title


# Borrow History
class BorrowHistory(models.Model):
    user = models.ForeignKey(UserRegister, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    borrow_date = models.DateField()
    due_date = models.DateField()
    return_date = models.DateField(blank=True, null=True)
    fine = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    notes = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user.name} borrowed {self.book.title}"


# Borrow Requests
class BorrowRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Cancelled', 'Cancelled'),
    ]
    user = models.ForeignKey(UserRegister, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    urgency = models.CharField(max_length=50, default='Medium')
    reason = models.TextField()
    notes = models.TextField(blank=True, null=True)
    request_date = models.DateField(auto_now_add=True)
    needed_by = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    admin_response = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Request: {self.book.title} by {self.user.name}"


# Notifications
class Notification(models.Model):
    user = models.ForeignKey(UserRegister, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.name}"


# System Settings
class SystemSettings(models.Model):
    max_borrow_days = models.IntegerField(default=7)
    fine_per_day = models.DecimalField(max_digits=5, decimal_places=2, default=0.50)
    open_time = models.TimeField(default='08:00')
    close_time = models.TimeField(default='17:00')
    contact_email = models.EmailField(default='admin@library.com')

    def __str__(self):
        return "System Settings"
