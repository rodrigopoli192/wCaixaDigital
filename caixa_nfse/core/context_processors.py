"""
Context processors for core app.
"""


def tenant_context(request):
    """Add tenant information to template context."""
    context = {
        "current_tenant": None,
    }

    if request.user.is_authenticated and hasattr(request.user, "tenant"):
        context["current_tenant"] = request.user.tenant

    return context
