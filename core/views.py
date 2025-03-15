from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView

def home(request):
    """Home page view"""
    return render(request, 'core/home.html')

def about(request):
    """About page view"""
    return render(request, 'core/about.html')

@login_required
def profile(request):
    """User profile view"""
    return render(request, 'core/profile.html')

class SignUpView(CreateView):
    """Sign up view for new users"""
    form_class = UserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'core/signup.html'
    
    def form_valid(self, form):
        messages.success(self.request, 'Account created successfully. You can now log in.')
        return super().form_valid(form)