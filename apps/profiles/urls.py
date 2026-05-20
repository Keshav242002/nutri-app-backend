from django.urls import path

from apps.profiles.views import OnboardingQuestionsView, OnboardingView, ProfileMeView

urlpatterns = [
    # onboarding/questions must come before onboarding to avoid URL shadowing
    path(
        "onboarding/questions",
        OnboardingQuestionsView.as_view(),
        name="profile-onboarding-questions",
    ),
    path("onboarding", OnboardingView.as_view(), name="profile-onboarding"),
    path("me", ProfileMeView.as_view(), name="profile-me"),
]
